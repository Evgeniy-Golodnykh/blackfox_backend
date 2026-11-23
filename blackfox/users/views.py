from django.contrib.auth import get_user_model
from djoser.views import UserViewSet
from rest_framework.serializers import ValidationError

from api.filters import UniversalUserCoachFilter
from coaching.access import visible

User = get_user_model()

admin_delete_message = 'Administrator users cannot be deleted'


class CustomUserViewSet(UserViewSet):
    """ViewSet for viewing and editing User instances."""

    filterset_class = UniversalUserCoachFilter

    def get_queryset(self):
        queryset = User.objects.select_related(
            'project_user__coach',
            'coach_profile',
        )
        if self.action in ('list', 'retrieve'):
            # Admins see everyone; a coach — their own clients; anyone
            # else — only themselves. (Coaches for everyone: /api/coaches/.)
            return visible(self.request.user, queryset, field='pk')
        return queryset

    def perform_destroy(self, instance):
        if instance.role == User.Roles.ADMIN:
            raise ValidationError(admin_delete_message)
        super().perform_destroy(instance)
