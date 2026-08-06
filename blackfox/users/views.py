from django.contrib.auth import get_user_model
from djoser.views import UserViewSet
from rest_framework.serializers import ValidationError

from api.filters import UniversalUserCoachFilter

User = get_user_model()

admin_delete_message = 'Administrator users cannot be deleted'


class CustomUserViewSet(UserViewSet):
    """ViewSet for viewing and editing User instances."""

    filterset_class = UniversalUserCoachFilter

    def perform_destroy(self, instance):
        if instance.role == User.Roles.ADMIN:
            raise ValidationError(admin_delete_message)
        super().perform_destroy(instance)
