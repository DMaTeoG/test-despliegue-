from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import FlockViewSet
from .views_weight import DailyWeightViewSet, ShedDashboardView
from .views_mortality import MortalityViewSet
from .views_conflict import SyncConflictViewSet
from .views import BreedReferenceViewSet
from .views_shipment import FlockShipmentViewSet

router = DefaultRouter()
router.register(r'flocks', FlockViewSet, basename='flock')
router.register(r'daily-weights', DailyWeightViewSet, basename='dailyweight')
router.register(r'mortality', MortalityViewSet, basename='mortality')
router.register(r'shipments', FlockShipmentViewSet, basename='flock-shipment')
# NOTE: We explicitly register the flocks-local conflicts under 'flocks-conflicts' to
# avoid a route name collision with the central `apps.sync` router which exposes
# the canonical `/api/conflicts/` endpoints. This keeps the public API stable and
# prevents ambiguous URL resolution in environments where both routers are included
# under the same `/api/` prefix. If you add another SyncConflictViewSet elsewhere,
# please choose a unique route and basename.
router.register(r'flocks-conflicts', SyncConflictViewSet, basename='flock-conflict')
router.register(r'references', BreedReferenceViewSet, basename='breedreference')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', ShedDashboardView.as_view(), name='shed-dashboard')
]
