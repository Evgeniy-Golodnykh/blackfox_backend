from rest_framework import viewsets

from api.filters import UniversalUserFilter
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
        queryset = CycleSettings.objects.select_related('user')
        if self.request.user.is_admin or self.request.user.is_coach:
            return queryset
        return queryset.filter(user=self.request.user)


class PeriodEntryViewSet(viewsets.ModelViewSet):
    """ViewSet for period entries."""

    serializer_class = PeriodEntrySerializer
    filterset_class = UniversalUserFilter
    http_method_names = ['get', 'post', 'head', 'options']

    def get_queryset(self):
        queryset = PeriodEntry.objects.select_related('user')
        if self.request.user.is_admin or self.request.user.is_coach:
            return queryset
        return queryset.filter(user=self.request.user)


class PhaseOverrideViewSet(viewsets.ModelViewSet):
    """ViewSet for phase overrides."""

    serializer_class = PhaseOverrideSerializer
    filterset_class = UniversalUserFilter

    def get_queryset(self):
        queryset = PhaseOverride.objects.select_related('user')
        if self.request.user.is_admin or self.request.user.is_coach:
            return queryset
        return queryset.filter(user=self.request.user)
