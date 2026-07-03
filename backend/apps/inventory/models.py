from django.db import models
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import ValidationError

from apps.farms.models import Farm, Shed


class InventoryItem(models.Model):
	"""Inventario inteligente por granja/galpón con métricas automáticas"""
	UNIT_CHOICES = [
		('KG', 'Kilogramos'),
		('TON', 'Toneladas'),
		('BAG', 'Sacos'),
		('LB', 'Libras')
	]

	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)
	current_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	unit = models.CharField(max_length=30, choices=UNIT_CHOICES)
	minimum_stock = models.DecimalField(max_digits=10, decimal_places=2, default=0)

	farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='inventory')
	shed = models.ForeignKey(Shed, on_delete=models.CASCADE, null=True, blank=True, related_name='inventory')

	daily_avg_consumption = models.DecimalField(max_digits=8, decimal_places=2, default=0)
	last_restock_date = models.DateField(null=True, blank=True)
	last_consumption_date = models.DateField(null=True, blank=True)

	alert_threshold_days = models.PositiveIntegerField(default=5)
	critical_threshold_days = models.PositiveIntegerField(default=2)

	class Meta:
		unique_together = ['name', 'farm', 'shed']

	def __str__(self):
		return f"{self.name} - {self.location_display}"

	@property
	def location_display(self):
		if self.shed:
			return f"{self.shed.name} ({self.farm.name})"
		return f"General - {self.farm.name}"

	@property
	def projected_stockout_date(self):
		if self.daily_avg_consumption and self.daily_avg_consumption > 0:
			days_remaining = float(self.current_stock) / float(self.daily_avg_consumption)
			return timezone.now().date() + timedelta(days=int(days_remaining))
		return None

	@property
	def stock_status(self):
		if float(self.current_stock) <= 0:
			return {'status': 'OUT_OF_STOCK', 'color': 'red', 'message': 'Sin stock'}

		# Verificar primero contra el stock mínimo definido
		current = float(self.current_stock)
		minimum = float(self.minimum_stock)
		
		# Si el stock actual está por debajo del mínimo
		if current < minimum:
			# Calcular qué tan crítico es (% del mínimo)
			percentage = (current / minimum * 100) if minimum > 0 else 0
			if percentage < 30:  # Menos del 30% del mínimo = crítico
				return {'status': 'CRITICAL', 'color': 'red', 'message': f'{current:.1f} {self.unit} (mín: {minimum:.1f})'}
			else:  # Entre 30% y 100% del mínimo = bajo stock
				return {'status': 'LOW', 'color': 'orange', 'message': f'{current:.1f} {self.unit} (mín: {minimum:.1f})'}
		
		# Si hay consumo promedio, usar cálculo basado en días (solo si estamos sobre el mínimo)
		if float(self.daily_avg_consumption) > 0 and current >= minimum:
			days_remaining = current / float(self.daily_avg_consumption)
			
			if days_remaining <= self.critical_threshold_days:
				return {'status': 'WARNING', 'color': 'amber', 'message': f'{days_remaining:.1f} días restantes'}
			elif days_remaining <= self.alert_threshold_days:
				return {'status': 'WARNING', 'color': 'amber', 'message': f'{days_remaining:.1f} días restantes'}
			else:
				return {'status': 'NORMAL', 'color': 'green', 'message': f'{days_remaining:.1f} días'}
		
		# Stock normal sin histórico de consumo
		return {'status': 'NORMAL', 'color': 'green', 'message': f'{current:.1f} {self.unit}'}

	def update_consumption_metrics(self):
		"""Actualiza el consumo diario promedio y la fecha del último consumo"""
		end_date = timezone.now().date()
		start_date = end_date - timedelta(days=30)
		
		total = self.consumption_records.filter(date__range=[start_date, end_date]).aggregate(
			total=models.Sum('quantity_consumed')
		)['total'] or 0

		# Promedio por día en los últimos 30 días
		self.daily_avg_consumption = float(total) / 30 if total else 0

		last = self.consumption_records.order_by('-date').first()
		if last:
			self.last_consumption_date = last.date

		self.save(update_fields=['daily_avg_consumption', 'last_consumption_date'])

	def add_stock(self, quantity, entry_date=None):
		"""Agregar stock creando un lote FIFO"""
		if entry_date is None:
			entry_date = timezone.now().date()
			
		# Crear lote FIFO
		batch = FoodBatch.objects.create(
			inventory_item=self,
			entry_date=entry_date,
			initial_quantity=quantity,
			current_quantity=quantity
		)
		
		# Actualizar stock total
		self.current_stock += quantity
		self.last_restock_date = entry_date
		self.save(update_fields=['current_stock', 'last_restock_date'])
		
		return batch

	def consume_fifo(self, quantity_to_consume, flock=None, user=None):
		"""Consumir usando FIFO estricto y retornar detalles de trazabilidad"""
		if quantity_to_consume <= 0:
			raise ValidationError("La cantidad a consumir debe ser mayor a 0")
			
		if float(self.current_stock) < float(quantity_to_consume):
			raise ValidationError(f"Stock insuficiente. Disponible: {self.current_stock}, Solicitado: {quantity_to_consume}")
		
		# Obtener lotes ordenados por fecha (FIFO)
		batches = self.food_batches.filter(current_quantity__gt=0).order_by('entry_date')
		
		remaining_to_consume = float(quantity_to_consume)
		fifo_details = []
		
		for batch in batches:
			if remaining_to_consume <= 0:
				break
				
			batch_available = float(batch.current_quantity)
			consume_from_batch = min(remaining_to_consume, batch_available)
			
			# Actualizar lote
			batch.current_quantity -= consume_from_batch
			batch.save()
			
			# Registrar detalle FIFO
			fifo_details.append({
				'batch_id': batch.id,
				'entry_date': batch.entry_date.isoformat(),
				'quantity_consumed': consume_from_batch,
				'batch_remaining': float(batch.current_quantity)
			})
			
			remaining_to_consume -= consume_from_batch
		
		# Actualizar stock total
		self.current_stock -= quantity_to_consume
		self.save(update_fields=['current_stock'])
		
		# Crear registro de consumo si se proporciona lote
		if flock:
			from apps.flocks.models import Flock
			if isinstance(flock, int):
				flock = Flock.objects.get(id=flock)
				
			consumption_record = FoodConsumptionRecord.objects.create(
				flock=flock,
				inventory_item=self,
				date=timezone.now().date(),
				quantity_consumed=quantity_to_consume,
				fifo_details=fifo_details,
				recorded_by=user or flock.created_by
			)
			
			return consumption_record, fifo_details
		
		return None, fifo_details


class FoodBatch(models.Model):
	"""Lote de alimento para implementar FIFO estricto"""
	inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='food_batches')
	entry_date = models.DateField()
	initial_quantity = models.DecimalField(max_digits=12, decimal_places=2)
	current_quantity = models.DecimalField(max_digits=12, decimal_places=2)
	supplier = models.CharField(max_length=100, blank=True)
	lot_number = models.CharField(max_length=50, blank=True)
	expiry_date = models.DateField(null=True, blank=True)
	invoice_number = models.CharField(max_length=100, blank=True, help_text="Número de factura")
	purchase_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.0, help_text="Valor de compra")
	
	class Meta:
		ordering = ['entry_date']
		indexes = [
			models.Index(fields=['inventory_item', 'entry_date']),
			models.Index(fields=['current_quantity'])
		]
	
	def __str__(self):
		return f"Lote {self.inventory_item.name} - {self.entry_date}"
	
	@property
	def is_depleted(self):
		return float(self.current_quantity) <= 0
	
	@property
	def consumption_rate(self):
		"""Porcentaje consumido del lote"""
		if float(self.initial_quantity) == 0:
			return 0
		return ((float(self.initial_quantity) - float(self.current_quantity)) / float(self.initial_quantity)) * 100


class FoodConsumptionRecord(models.Model):
	"""Registro de consumo de alimento por lote con trazabilidad FIFO completa"""
	flock = models.ForeignKey('flocks.Flock', on_delete=models.CASCADE, related_name='food_consumption_records')
	inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='flock_consumption_records')
	date = models.DateField()
	quantity_consumed = models.DecimalField(max_digits=12, decimal_places=2)
	fifo_details = models.JSONField(help_text="Detalles de qué lotes se consumieron")
	recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
	
	# Campos para sincronización offline
	client_id = models.CharField(max_length=50, null=True, blank=True)
	sync_status = models.CharField(max_length=20, default='SYNCED')
	created_by_device = models.CharField(max_length=100, null=True, blank=True)
	
	class Meta:
		unique_together = ['flock', 'inventory_item', 'date']
		indexes = [
			models.Index(fields=['date', 'flock']),
			models.Index(fields=['sync_status'])
		]
	
	def __str__(self):
		return f"Consumo {self.inventory_item.name} - {self.flock} - {self.date}"
	
	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		# Actualizar métricas del item de inventario
		try:
			self.inventory_item.update_consumption_metrics()
		except Exception:
			pass


class InventoryConsumptionRecord(models.Model):
	"""Registro diario de consumo de un item de inventario (para métricas generales)"""
	inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='consumption_records')
	date = models.DateField()
	quantity_consumed = models.DecimalField(max_digits=12, decimal_places=2)

	class Meta:
		unique_together = ['inventory_item', 'date']

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		# Después de guardar, actualizar métricas en el item
		try:
			self.inventory_item.update_consumption_metrics()
		except Exception:
			pass



# Create your models here.
