from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.db import transaction

from .models import FlockShipment, Flock
from .serializers_shipment import FlockShipmentSerializer


class IsFlockShipmentAuthorized(permissions.BasePermission):
    """Permisos específicos para la saca/despacho de lotes"""
    
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        if user.is_staff:
            return True
            
        role_name = getattr(getattr(user, 'role', None), 'name', None)
        if role_name == 'Administrador Sistema':
            return True
            
        if request.method == 'POST':
            flock_id = request.data.get('flock')
            if not flock_id:
                return False
            try:
                flock = Flock.objects.get(pk=flock_id)
            except Flock.DoesNotExist:
                return False
                
            if role_name == 'Galponero':
                return flock.shed.assigned_worker == user
            if role_name == 'Administrador de Granja':
                return flock.shed.farm.farm_manager == user
            return False
            
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user
        role_name = getattr(getattr(user, 'role', None), 'name', None)
        
        if user.is_staff or role_name == 'Administrador Sistema':
            return True
            
        flock = obj.flock
        if role_name == 'Galponero':
            return flock.shed.assigned_worker == user
        if role_name == 'Administrador de Granja':
            return flock.shed.farm.farm_manager == user
            
        return False


class FlockShipmentViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar despachos a planta procesadora (Hoja PESAS)"""
    queryset = FlockShipment.objects.all()
    serializer_class = FlockShipmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsFlockShipmentAuthorized]

    def get_queryset(self):
        user = self.request.user
        role_name = getattr(getattr(user, 'role', None), 'name', None)
        
        qs = FlockShipment.objects.all()
        
        # Filtros de query parameters
        flock_param = self.request.query_params.get('flock')
        if flock_param:
            qs = qs.filter(flock_id=flock_param)
            
        invoice_param = self.request.query_params.get('invoice_number')
        if invoice_param:
            qs = qs.filter(invoice_number__icontains=invoice_param)

        # Scoping según el rol
        if user.is_staff or role_name == 'Administrador Sistema':
            return qs
        if role_name == 'Administrador de Granja':
            return qs.filter(flock__shed__farm__farm_manager=user)
        if role_name == 'Galponero':
            return qs.filter(flock__shed__assigned_worker=user)

        return FlockShipment.objects.none()

    def perform_create(self, serializer):
        with transaction.atomic():
            serializer.save()
