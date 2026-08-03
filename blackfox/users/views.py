from djoser.views import UserViewSet

from api.filters import UniversalUserCoachFilter


class CustomUserViewSet(UserViewSet):
    """ViewSet for viewing and editing User instances."""

    filterset_class = UniversalUserCoachFilter
