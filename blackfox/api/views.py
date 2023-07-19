from rest_framework import viewsets, filters
from rest_framework.permissions import SAFE_METHODS, IsAuthenticatedOrReadOnly

from api.serializers import (DietSerializer, DietPostSerializer,
                             MeasurementSerializer, ProjectSerializer)
from api.permissions import IsCoach
from training.models import Diet, Anthropometry, Project


class DietViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = DietSerializer
    queryset = Diet.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'diet_date']

    def get_serializer_class(self):
        if self.request.method in SAFE_METHODS:
            return DietSerializer
        return DietPostSerializer


class MeasurementViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = MeasurementSerializer
    queryset = Anthropometry.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'measurement_date']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsCoach]
    serializer_class = ProjectSerializer
    queryset = Project.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'coach', 'start_date']

    def perform_create(self, serializer):
        serializer.save(trainer=self.request.user)
