from rest_framework import viewsets, filters
from rest_framework.permissions import SAFE_METHODS, IsAuthenticatedOrReadOnly

from api.serializers import DietSerializer, DietPostSerializer
from training.models import Diet


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
