from rest_framework.routers import DefaultRouter

from cycles.views import (
    CycleSettingsViewSet, PeriodEntryViewSet, PhaseOverrideViewSet,
)

router = DefaultRouter()
router.register('settings', CycleSettingsViewSet, basename='cycle-settings')
router.register('periods', PeriodEntryViewSet, basename='cycle-periods')
router.register('overrides', PhaseOverrideViewSet, basename='cycle-overrides')

urlpatterns = router.urls
