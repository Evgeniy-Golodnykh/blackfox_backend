from rest_framework import viewsets

from api.filters import UniversalUserFilter
from coaching.access import visible
from cycles.models import CycleSettings, PeriodEntry, PhaseOverride
from cycles.serializers import (
    CycleSettingsSerializer, PeriodEntrySerializer, PhaseOverrideSerializer,
)


class CycleSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for cycle settings."""

    serializer_class = CycleSettingsSerializer
    filterset_class = UniversalUserFilter
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return visible(self.request.user,
                       CycleSettings.objects.select_related('user'))


class PeriodEntryViewSet(viewsets.ModelViewSet):
    """ViewSet for period entries."""

    serializer_class = PeriodEntrySerializer
    filterset_class = UniversalUserFilter
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        return visible(self.request.user,
                       PeriodEntry.objects.select_related('user'))


class PhaseOverrideViewSet(viewsets.ModelViewSet):
    """ViewSet for phase overrides."""

    serializer_class = PhaseOverrideSerializer
    filterset_class = UniversalUserFilter

    def get_queryset(self):
        return visible(self.request.user,
                       PhaseOverride.objects.select_related('user'))
