from rest_framework import serializers
from django.core.exceptions import ValidationError
from .models import FlockShipment, Flock


class FlockShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlockShipment
        fields = [
            'id', 'flock', 'date', 'invoice_number', 'males_count', 'females_count', 'total_birds',
            'average_weight_farm', 'total_weight_farm', 'dead_in_transit', 'birds_received_plant',
            'average_weight_plant', 'total_weight_plant', 'plant_shrinkage_grams', 'birds_sold',
            'discount_kilos', 'total_weight_sold', 'average_weight_sold', 'total_shrinkage_grams',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, data):
        flock = data.get('flock')
        males = data.get('males_count')
        females = data.get('females_count')
        total = data.get('total_birds')
        
        # Validar consistencia de conteos
        if total is not None and males is not None and females is not None:
            if total != (males + females):
                raise serializers.ValidationError(
                    "El total de aves despachadas debe ser igual a la suma de machos y hembras (males_count + females_count)"
                )
        
        # En creación, validar que no exceda la cantidad actual del lote
        is_new = self.instance is None
        if is_new and flock and total:
            if total > flock.current_quantity:
                raise serializers.ValidationError(
                    f"La cantidad despachada ({total}) supera la población actual del lote ({flock.current_quantity})"
                )

        # Validar que los pesos sean valores lógicos
        if data.get('average_weight_farm') and data.get('average_weight_farm') <= 0:
            raise serializers.ValidationError("El peso promedio en granja debe ser mayor a 0")
        
        if data.get('average_weight_plant') and data.get('average_weight_plant') <= 0:
            raise serializers.ValidationError("El peso promedio en planta debe ser mayor a 0")

        # Validaciones de permisos por rol
        user = self.context['request'].user
        role_name = getattr(getattr(user, 'role', None), 'name', None)
        
        if role_name == 'Galponero':
            if flock.shed.assigned_worker != user:
                raise serializers.ValidationError("No tienes permisos para registrar despachos en este galpón")
        elif role_name == 'Administrador de Granja':
            if flock.shed.farm.farm_manager != user:
                raise serializers.ValidationError("No tienes permisos para registrar despachos en esta granja")

        return data
