from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from api.permissions import IsAdmin, IsCoach
from api.serializers import (
    BodyStatsDiarySerializer, CreateUpdateBodyStatsDiarySerializer,
    CreateUpdateFoodDiarySerializer, CreateUpdateProjectSerializer,
    FoodDiarySerializer, ProjectSerializer,
)
from training.models import BodyStatsDiary, FoodDiary, Project


class BodyStatsDiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'date']

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return CreateUpdateBodyStatsDiarySerializer
        return BodyStatsDiarySerializer

    def get_queryset(self):
        if self.request.user.role == 'user':
            return BodyStatsDiary.objects.filter(user=self.request.user)
        return BodyStatsDiary.objects.all()


class FoodDiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'date']

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return CreateUpdateFoodDiarySerializer
        return FoodDiarySerializer

    def get_queryset(self):
        if self.request.user.role == 'user':
            return FoodDiary.objects.filter(user=self.request.user)
        return FoodDiary.objects.all()


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin | IsCoach]
    queryset = Project.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'coach', 'start_date']

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return CreateUpdateProjectSerializer
        return ProjectSerializer
