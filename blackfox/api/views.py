from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import filters, status, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from api.permissions import IsAdmin, IsAdminOrCoach
from api.serializers import (
    BodyStatsDiarySerializer, CreateUpdateBodyStatsDiarySerializer,
    CreateUpdateProjectSerializer, FoodDiarySerializer, ProjectSerializer,
)
from fatsecret.tools import get_fooddiary_objects
from training.models import BodyStatsDiary, FoodDiary, Project

User = get_user_model()
fatsecret_account_not_exists_message = 'Please link your Fatsecret account'
fatsecret_error_message = 'Fatsecret error: {error}'
project_not_exists_message = 'Please create a project for current user'


class BodyStatsDiaryViewSet(viewsets.ModelViewSet):
    queryset = BodyStatsDiary.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter]
    search_fields = ('=user__username',)

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return CreateUpdateBodyStatsDiarySerializer
        return BodyStatsDiarySerializer


class FoodDiaryViewSet(viewsets.ModelViewSet):
    queryset = FoodDiary.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly]
    serializer_class = FoodDiarySerializer
    filter_backends = [filters.SearchFilter]
    search_fields = ('=user__username',)

    def create(self, request):
        username = request.query_params.get('user')
        if username:
            user = get_object_or_404(User, username=username)
        else:
            user = request.user
        if not user.fatsecret_token or not user.fatsecret_secret:
            return Response(
                {'message': fatsecret_account_not_exists_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not Project.objects.filter(user=user).exists():
            return Response(
                {'message': project_not_exists_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            objs = get_fooddiary_objects(user)
        except KeyError as error:
            return Response(
                {'message': fatsecret_error_message.format(error=error)},
                status=status.HTTP_400_BAD_REQUEST
            )
        FoodDiary.objects.bulk_create(objs=objs)
        return Response(FoodDiarySerializer(objs, many=True).data)


class ProjectViewSet(viewsets.ModelViewSet):
    filter_backends = [filters.SearchFilter]
    search_fields = ('=user__username',)

    def get_permissions(self):
        if self.action == 'create':
            return [IsAdmin()]
        return [IsAdminOrCoach()]

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return CreateUpdateProjectSerializer
        return ProjectSerializer

    def get_queryset(self):
        if self.request.user.is_coach:
            return Project.objects.filter(coach=self.request.user)
        return Project.objects.all()
