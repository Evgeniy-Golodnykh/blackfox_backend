from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.filters import UniversalUserCoachFilter, UniversalUserFilter
from api.permissions import IsAdminOrCoach
from coaching.access import can_view, target_user, visible
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

    filterset_class = UniversalUserFilter

    def get_serializer_class(self):
        if self.action in ('create', 'partial_update'):
            return CreateUpdateBodyStatsDiarySerializer
        return BodyStatsDiarySerializer

    def get_queryset(self):
        return visible(self.request.user,
                       BodyStatsDiary.objects.select_related('user'))

    def perform_create(self, serializer):
        serializer.save(user=target_user(self.request))


class FoodDiaryViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing FoodDiary instances."""

    serializer_class = FoodDiarySerializer
    filterset_class = UniversalUserFilter

    def get_queryset(self):
        return visible(self.request.user,
                       FoodDiary.objects.select_related('user'))

    def create(self, request):
        user = target_user(request)
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
        queryset = Project.objects.select_related('user', 'coach')
        if self.request.user.is_admin:
            return queryset
        if self.request.user.is_coach:
            return queryset.filter(coach=self.request.user)
        return queryset.filter(user=self.request.user)

    def check_coach_rights(self, serializer):
        """A coach plans only for their own clients and only as themselves;
        moving a client to another coach is an admin's job."""

        viewer = self.request.user
        if viewer.is_admin:
            return
        data = serializer.validated_data
        coach = data.get('coach', getattr(serializer.instance, 'coach', None))
        user = data.get('user', getattr(serializer.instance, 'user', None))
        if coach != viewer or (user is not None and not can_view(viewer,
                                                                 user)):
            raise PermissionDenied('Это не ваш клиент.')

    def perform_create(self, serializer):
        self.check_coach_rights(serializer)
        serializer.save()

    def perform_update(self, serializer):
        self.check_coach_rights(serializer)
        serializer.save()
