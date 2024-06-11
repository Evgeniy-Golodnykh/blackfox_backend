from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from api.permissions import IsAdmin, IsCoach
from api.serializers import FitnessDiarySerializer, ProjectSerializer
from training.models import FitnessDiary, Project


class FitnessDiaryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = FitnessDiarySerializer
    queryset = FitnessDiary.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'date']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProjectViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin, IsCoach]
    serializer_class = ProjectSerializer
    queryset = Project.objects.all()
    filter_backends = [filters.SearchFilter]
    search_fields = ['user', 'coach', 'start_date']

    def perform_create(self, serializer):
        serializer.save(trainer=self.request.user)
