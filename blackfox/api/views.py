from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from api.permissions import IsAdmin, IsCoach
from api.serializers import (
    BodyStatsDiarySerializer, CreateUpdateProjectSerializer,
    FoodDiarySerializer, ProjectSerializer,
)
from training.models import BodyStatsDiary, FoodDiary, Project


class BodyStatsDiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = BodyStatsDiarySerializer
    queryset = BodyStatsDiary.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'date']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FoodDiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = FoodDiarySerializer
    queryset = FoodDiary.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'date']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin | IsCoach]
    queryset = Project.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'coach', 'start_date']

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return CreateUpdateProjectSerializer
        return ProjectSerializer
