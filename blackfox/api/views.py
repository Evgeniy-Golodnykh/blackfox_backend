from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.filters import UniversalUserCoachFilter, UniversalUserFilter
from api.permissions import IsAdmin, IsAdminOrCoach
from content.models import Article, Video
from content.serializers import ArticleSerializer, VideoSerializer
from fatsecret.tools import get_fooddiary_objects
from training.models import BodyStatsDiary, FoodDiary, Project
from training.serializers import (
    BodyStatsDiarySerializer, CreateUpdateBodyStatsDiarySerializer,
    CreateUpdateProjectSerializer, FoodDiarySerializer, ProjectSerializer,
)

User = get_user_model()

fatsecret_account_not_exists_message = 'Please link your Fatsecret account'
fatsecret_error_message = 'Fatsecret error: {error}'
fooddiary_objects_create_message = 'Fooddiary objects successfully created'
project_not_exists_message = 'Please create a project for current user'


class BodyStatsDiaryViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing BodyStatsDiary instances."""

    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = UniversalUserFilter

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return CreateUpdateBodyStatsDiarySerializer
        return BodyStatsDiarySerializer

    def get_queryset(self):
        if self.request.user.is_admin or self.request.user.is_coach:
            return BodyStatsDiary.objects.all()
        return BodyStatsDiary.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        if self.request.user.is_admin or self.request.user.is_coach:
            user = get_object_or_404(
                User, username=self.request.query_params.get('user')
            )
        else:
            user = self.request.user
        serializer.save(user=user)


class FoodDiaryViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing FoodDiary instances."""

    permission_classes = [IsAuthenticated]
    serializer_class = FoodDiarySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = UniversalUserFilter

    def get_queryset(self):
        if self.request.user.is_admin or self.request.user.is_coach:
            return FoodDiary.objects.all()
        return FoodDiary.objects.filter(user=self.request.user)

    def create(self, request):
        if request.user.is_admin or request.user.is_coach:
            user = get_object_or_404(
                User, username=request.query_params.get('user')
            )
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
            reload = True if request.query_params.get('reload') else False
            objs = get_fooddiary_objects(user, reload=reload)
        except KeyError as error:
            return Response(
                {'message': fatsecret_error_message.format(error=error)},
                status=status.HTTP_400_BAD_REQUEST
            )
        FoodDiary.objects.bulk_create(objs=objs)
        return Response(
            {'message': fooddiary_objects_create_message},
            status=status.HTTP_201_CREATED
        )


class ProjectViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Project instances."""

    filter_backends = [DjangoFilterBackend]
    filterset_class = UniversalUserCoachFilter

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdminOrCoach()]

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update', 'update'):
            return CreateUpdateProjectSerializer
        return ProjectSerializer

    def get_queryset(self):
        if self.request.user.is_admin:
            return Project.objects.all()
        if self.request.user.is_coach:
            return Project.objects.filter(coach=self.request.user)
        return Project.objects.filter(user=self.request.user)


class ArticleViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Article instances."""

    queryset = Article.objects.all()
    serializer_class = ArticleSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdmin()]


class VideoViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Video instances."""

    queryset = Video.objects.all()
    serializer_class = VideoSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdmin()]
