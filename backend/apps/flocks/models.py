from django.db import models
from django.utils import timezone
from django.conf import settings

from apps.farms.models import Shed
from django.conf import settings


class BaseModel(models.Model):
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class Flock(BaseModel):
	"""Lote de pollos con control de estados"""
	GENDER_CHOICES = [
		('M', 'Macho'),
		('F', 'Hembra'),
		('X', 'Mixto'),
	]
	STATUS_CHOICES = [
		('ACTIVE', 'Activo'),
		('SOLD', 'Vendido'),
		('FINISHED', 'Terminado'),
		('TRANSFERRED', 'Transferido'),
	]

	# Datos iniciales del lote
	arrival_date = models.DateField()
	initial_quantity = models.PositiveIntegerField()
	current_quantity = models.PositiveIntegerField()
	initial_weight = models.DecimalField(max_digits=6, decimal_places=2)

	# Umbrales personalizables por lote (opcionales)
	weight_alert_low = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	weight_alert_high = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	breed = models.CharField(max_length=50)
	gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
	supplier = models.CharField(max_length=100)

	# Relaciones
	shed = models.ForeignKey(Shed, on_delete=models.CASCADE, related_name='flocks')
	status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='ACTIVE')
	estimated_exit_date = models.DateField(null=True, blank=True)
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_flocks')

	def __str__(self):
		return f"Lote {self.id} - {self.breed} ({self.shed.name})"

	# Campos calculados útiles
	@property
	def current_age_days(self):
		return (timezone.now().date() - self.arrival_date).days

	@property
	def survival_rate(self):
		if self.initial_quantity == 0:
			return 0
		return (self.current_quantity / self.initial_quantity) * 100

	def save(self, *args, **kwargs):
		# Auto-setear current_quantity en creación
		if not self.pk and (self.current_quantity is None or self.current_quantity == 0):
			self.current_quantity = self.initial_quantity
		
		# Validar capacidad del galpón antes de crear nuevo lote
		if not self.pk:  # Solo en creación
			self._validate_shed_capacity()
		
		super().save(*args, **kwargs)
	
	def _validate_shed_capacity(self):
		"""Validar que el galpón tenga suficiente capacidad para el nuevo lote"""
		if not self.shed or not hasattr(self.shed, 'capacity'):
			return  # Si no hay galpón o capacidad definida, no validar
		
		# Calcular capacidad actual ocupada en el galpón
		current_occupation = Flock.objects.filter(
			shed=self.shed,
			status='ACTIVE'
		).aggregate(
			total=models.Sum('current_quantity')
		)['total'] or 0
		
		# Verificar si el nuevo lote excede la capacidad
		if current_occupation + self.initial_quantity > self.shed.capacity:
			from django.core.exceptions import ValidationError
			raise ValidationError(
				f'El galpón {self.shed.name} no tiene suficiente capacidad. '
				f'Capacidad: {self.shed.capacity}, Ocupado: {current_occupation}, '
				f'Nuevo lote: {self.initial_quantity}'
			)


class BreedReference(BaseModel):
	"""Tabla de referencia de peso y consumo por raza y edad (días) con versionado"""
	breed = models.CharField(max_length=100)
	age_days = models.PositiveIntegerField()
	expected_weight = models.DecimalField(max_digits=6, decimal_places=2)
	expected_consumption = models.DecimalField(max_digits=6, decimal_places=2, default=0)  # gramos/ave/día
	tolerance_range = models.DecimalField(max_digits=5, decimal_places=2, default=10.0)  # porcentaje

	# Versionado para actualizaciones
	version = models.PositiveIntegerField(default=1)
	is_active = models.BooleanField(default=True)
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)

	class Meta:
		unique_together = ['breed', 'age_days', 'version']
		ordering = ['breed', 'age_days']

	@classmethod
	def get_reference_for_flock(cls, flock, date=None):
		"""Obtener referencia para un lote en una fecha específica"""
		if date is None:
			date = timezone.now().date()

		age_days = (date - flock.arrival_date).days

		return cls.objects.filter(
			breed=flock.breed,
			age_days=age_days,
			is_active=True
		).order_by('-version').first()


class DailyWeightRecord(BaseModel):
	flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='weight_records')
	date = models.DateField()
	average_weight = models.DecimalField(max_digits=6, decimal_places=2)
	sample_size = models.PositiveIntegerField(default=10)
	recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

	expected_weight = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
	deviation_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

	client_id = models.CharField(max_length=50, null=True, blank=True)
	sync_status = models.CharField(max_length=20, default='SYNCED')
	created_by_device = models.CharField(max_length=100, null=True, blank=True)

	class Meta:
		unique_together = ['flock', 'date']

	def save(self, *args, **kwargs):
		# Calcular peso esperado y desviación automáticamente
		if not self.expected_weight or self.expected_weight == 0:
			self.expected_weight = self._calculate_expected_weight()

		if self.expected_weight and self.expected_weight > 0:
			deviation = abs(self.average_weight - self.expected_weight)
			try:
				self.deviation_percentage = (deviation / self.expected_weight) * 100
			except Exception:
				self.deviation_percentage = None
		
		# Guardar primero el registro
		super().save(*args, **kwargs)
		
		# Verificar si se debe generar alarma por desviación
		self._check_weight_deviation_alarm()

	def _calculate_expected_weight(self):
		"""Calcular peso esperado usando BreedReference más inteligente"""
		# Usar el método de clase que maneja versionado
		reference = BreedReference.get_reference_for_flock(self.flock, self.date)
		return reference.expected_weight if reference else None
	
	def _check_weight_deviation_alarm(self):
		"""Verificar si el peso está fuera del rango aceptable y generar alarma"""
		if not self.expected_weight or not self.deviation_percentage:
			return
		
		try:
			from apps.alarms.models import AlarmConfiguration, Alarm
		except ImportError:
			return
			
		# Obtener referencia para verificar tolerancia
		reference = BreedReference.get_reference_for_flock(self.flock, self.date)
		if not reference:
			return
			
		tolerance = float(reference.tolerance_range)
		
		# Si la desviación supera la tolerancia, crear alarma
		if float(self.deviation_percentage) > tolerance:
			# Verificar configuración de alarmas de la granja
			config = AlarmConfiguration.objects.filter(
				alarm_type='WEIGHT_DEVIATION',
				farm=self.flock.shed.farm,
				is_active=True
			).first()
			
			if config:
				# Verificar si no existe alarma similar reciente
				recent_alarms = Alarm.objects.filter(
					alarm_type='WEIGHT_DEVIATION',
					entity_type='FLOCK',
					entity_id=self.flock.id,
					status='PENDING',
					created_at__date=self.date
				)
				
				if not recent_alarms.exists():
					priority = 'HIGH' if float(self.deviation_percentage) > (tolerance * 2) else 'MEDIUM'
					
					Alarm.objects.create(
						alarm_type='WEIGHT_DEVIATION',
						entity_type='FLOCK',
						entity_id=self.flock.id,
						priority=priority,
						title=f'Peso fuera de rango - {self.flock}',
						message=f'Peso promedio {self.average_weight}g vs esperado {self.expected_weight}g. Desviación: {self.deviation_percentage:.1f}%',
						farm=self.flock.shed.farm,
						shed=self.flock.shed,
						data={
							'flock_id': self.flock.id,
							'date': self.date.isoformat(),
							'actual_weight': float(self.average_weight),
							'expected_weight': float(self.expected_weight),
							'deviation_percentage': float(self.deviation_percentage),
							'tolerance_range': tolerance,
							'breed': self.flock.breed
						}
					)

	def _calculate_expected_weight(self):
		age_days = (self.date - self.flock.arrival_date).days
		reference = BreedReference.objects.filter(
			breed=self.flock.breed,
			age_days=age_days,
			is_active=True
		).order_by('-version').first()

		return reference.expected_weight if reference else None


class MortalityCause(BaseModel):
	"""Catálogo de causas de mortalidad"""
	name = models.CharField(max_length=100, unique=True)
	category = models.CharField(max_length=50, choices=[
		('DISEASE', 'Enfermedad'),
		('ENVIRONMENTAL', 'Ambiental'),
		('NUTRITIONAL', 'Nutricional'),
		('UNKNOWN', 'Desconocida'),
		('OTHER', 'Otra'),
	])
	requires_veterinary = models.BooleanField(default=False)
	is_active = models.BooleanField(default=True)


class MortalityRecord(BaseModel):
	"""Registro de mortalidad con actualización automática del lote"""
	flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='mortality_records')
	date = models.DateField()
	deaths = models.PositiveIntegerField()
	selection = models.PositiveIntegerField(default=0)
	cause = models.ForeignKey(MortalityCause, on_delete=models.SET_NULL, null=True, blank=True)
	recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

	# Campos para análisis
	temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
	notes = models.TextField(blank=True)

	client_id = models.CharField(max_length=50, null=True, blank=True)
	sync_status = models.CharField(max_length=20, default='SYNCED')
	created_by_device = models.CharField(max_length=100, null=True, blank=True)

	class Meta:
		unique_together = ['flock', 'date']

	def save(self, *args, **kwargs):
		is_new = not self.pk

		if is_new:
			total_losses = self.deaths + self.selection
			# Validar que no exceda cantidad actual
			if total_losses > self.flock.current_quantity:
				from django.core.exceptions import ValidationError
				raise ValidationError(
					f"Bajas totales ({total_losses}) excede cantidad actual del lote ({self.flock.current_quantity})"
				)

			# Actualizar lote
			self.flock.current_quantity -= total_losses
			self.flock.save(update_fields=['current_quantity'])

		super().save(*args, **kwargs)

		# Verificar alarmas después de guardar
		if is_new:
			try:
				self._check_mortality_alarms()
			except Exception:
				# no dejar que una falla en alarmas rompa el guardado
				pass

	def _check_mortality_alarms(self):
		"""Verificar si debe generar alarma por mortalidad alta"""
		from datetime import timedelta
		from django.core.exceptions import ObjectDoesNotExist

		original_quantity = self.flock.current_quantity + self.deaths
		if original_quantity == 0:
			return

		daily_mortality_rate = (self.deaths / original_quantity) * 100

		# Obtener configuración de alarma de la granja
		try:
			from apps.alarms.models import AlarmConfiguration, Alarm
		except Exception:
			return

		config = AlarmConfiguration.objects.filter(
			alarm_type='MORTALITY',
			farm=self.flock.shed.farm,
			is_active=True
		).first()

		if config and daily_mortality_rate >= config.threshold_value:
			priority = 'HIGH' if daily_mortality_rate >= (getattr(config, 'critical_threshold', None) or config.threshold_value * 2) else 'MEDIUM'

			Alarm.objects.create(
				alarm_type='MORTALITY',
				description=f'Mortalidad alta en {self.flock.shed.name}: {daily_mortality_rate:.1f}% (umbral: {config.threshold_value}%)',
				priority=priority,
				flock=self.flock
			)


class SyncConflict(BaseModel):
	"""Registro de conflictos detectados durante sincronización offline"""
	source = models.CharField(max_length=50)  # e.g. 'daily_weight', 'mortality'
	client_id = models.CharField(max_length=100, null=True, blank=True)
	payload = models.JSONField()
	resolution = models.CharField(max_length=50, null=True, blank=True)  # e.g. 'manual', 'discarded', 'merged'
	resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
	resolved_at = models.DateTimeField(null=True, blank=True)

	# Optional link to domain objects
	flock = models.ForeignKey(Flock, null=True, blank=True, on_delete=models.SET_NULL)

	class Meta:
		indexes = [models.Index(fields=['source', 'client_id']), models.Index(fields=['resolved_at'])]


class ReferenceImportLog(BaseModel):
	"""Log de importaciones de tablas de referencia"""
	file_name = models.CharField(max_length=255)
	imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	total_rows = models.PositiveIntegerField(default=0)
	successful_imports = models.PositiveIntegerField(default=0)
	updates = models.PositiveIntegerField(default=0)
	errors = models.PositiveIntegerField(default=0)
	error_details = models.JSONField(default=list)


class FlockShipment(BaseModel):
	"""Registro de despacho y venta del lote a planta procesadora (Hoja PESAS)"""
	flock = models.ForeignKey(Flock, on_delete=models.CASCADE, related_name='shipments')
	date = models.DateField(help_text="Fecha de despacho")
	invoice_number = models.CharField(max_length=50, help_text="Número de planilla/factura")
	males_count = models.PositiveIntegerField(null=True, blank=True, help_text="Cantidad de machos despachados")
	females_count = models.PositiveIntegerField(null=True, blank=True, help_text="Cantidad de hembras despachadas")
	total_birds = models.PositiveIntegerField(help_text="Total aves despachadas")
	average_weight_farm = models.DecimalField(max_digits=6, decimal_places=2, help_text="Peso promedio en granja (kg)")
	total_weight_farm = models.DecimalField(max_digits=10, decimal_places=2, help_text="Kilos totales en granja")
	dead_in_transit = models.PositiveIntegerField(default=0, help_text="Aves ahogadas en tránsito")
	birds_received_plant = models.PositiveIntegerField(help_text="Pollos recibidos en planta")
	average_weight_plant = models.DecimalField(max_digits=6, decimal_places=2, help_text="Peso promedio en planta (kg)")
	total_weight_plant = models.DecimalField(max_digits=10, decimal_places=2, help_text="Kilos recibidos en planta")
	plant_shrinkage_grams = models.DecimalField(max_digits=6, decimal_places=2, help_text="Merma de planta en gramos por pollo")
	birds_sold = models.PositiveIntegerField(help_text="Pollos vendidos")
	discount_kilos = models.DecimalField(max_digits=8, decimal_places=2, default=0.0, help_text="Kilos descontados")
	total_weight_sold = models.DecimalField(max_digits=10, decimal_places=2, help_text="Kilos netos de venta")
	average_weight_sold = models.DecimalField(max_digits=6, decimal_places=2, help_text="Peso promedio de venta (kg)")
	total_shrinkage_grams = models.DecimalField(max_digits=6, decimal_places=2, help_text="Merma total en gramos")
	notes = models.TextField(blank=True, help_text="Observaciones de liquidación")

	def __str__(self):
		return f"Despacho {self.invoice_number} - Lote {self.flock.id} - {self.date}"

	def save(self, *args, **kwargs):
		# Auto-calcular campos basados en fórmulas de la planilla si no están definidos
		if not self.total_birds:
			self.total_birds = (self.males_count or 0) + (self.females_count or 0)
		
		if not self.total_weight_farm or self.total_weight_farm == 0:
			from decimal import Decimal
			self.total_weight_farm = Decimal(str(self.total_birds)) * Decimal(str(self.average_weight_farm))
		
		if not self.birds_received_plant:
			self.birds_received_plant = max(0, self.total_birds - self.dead_in_transit)

		if (not self.plant_shrinkage_grams or self.plant_shrinkage_grams == 0) and self.birds_received_plant > 0:
			from decimal import Decimal
			# (kilos granja - kilos planta) / pollos planta * 1000
			diff_kilos = Decimal(str(self.total_weight_farm)) - Decimal(str(self.total_weight_plant))
			self.plant_shrinkage_grams = (diff_kilos / Decimal(str(self.birds_received_plant))) * Decimal('1000')

		if not self.birds_sold:
			self.birds_sold = self.birds_received_plant

		if not self.average_weight_sold and self.birds_sold > 0:
			from decimal import Decimal
			self.average_weight_sold = Decimal(str(self.total_weight_sold)) / Decimal(str(self.birds_sold))

		if (not self.total_shrinkage_grams or self.total_shrinkage_grams == 0) and self.birds_received_plant > 0:
			from decimal import Decimal
			# (kilos granja - kilos venta) / pollos planta * 1000
			diff_kilos_total = Decimal(str(self.total_weight_farm)) - Decimal(str(self.total_weight_sold))
			self.total_shrinkage_grams = (diff_kilos_total / Decimal(str(self.birds_received_plant))) * Decimal('1000')

		is_new = not self.pk
		if is_new:
			# Validar que no despache más de los que hay disponibles
			if self.total_birds > self.flock.current_quantity:
				from django.core.exceptions import ValidationError
				raise ValidationError(
					f"La cantidad despachada ({self.total_birds}) supera la población actual del lote ({self.flock.current_quantity})"
				)
			
			# Descontar del lote
			self.flock.current_quantity -= self.total_birds
			if self.flock.current_quantity == 0:
				self.flock.status = 'SOLD'
			self.flock.save(update_fields=['current_quantity', 'status'])

		super().save(*args, **kwargs)
