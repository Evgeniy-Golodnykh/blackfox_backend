from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from checkins.models import DailyCheckin
from checkins.serializers import CheckinSerializer
from training.models import Project

User = get_user_model()

HISTORY_DAYS = 60

only_clients_message = 'Чек-ин отмечает только клиент.'
not_your_client_message = 'Это не ваш клиент.'


def can_read(viewer, username):
    if viewer.is_admin or viewer.username == username:
        return True
    if viewer.is_coach:
        return Project.objects.filter(
            coach=viewer, user__username=username,
        ).exists()
    return False


class CheckinsView(APIView):
    """GET /api/checkins/?user=<username> — last 60 days, newest first.
    POST /api/checkins/ — the client's own check-in for a day (upsert)."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        username = request.query_params.get('user') or request.user.username
        if not can_read(request.user, username):
            return Response({'detail': not_your_client_message},
                            status=status.HTTP_403_FORBIDDEN)
        since = timezone.localdate() - timedelta(days=HISTORY_DAYS)
        checkins = DailyCheckin.objects.filter(
            user__username=username, date__gte=since,
        ).select_related('user')
        return Response(CheckinSerializer(checkins, many=True).data)

    def post(self, request):
        if request.user.role != User.Roles.USER:
            return Response({'detail': only_clients_message},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = CheckinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        date = data.pop('date')
        checkin, created = DailyCheckin.objects.update_or_create(
            user=request.user, date=date, defaults=data,
        )
        return Response(
            CheckinSerializer(checkin).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
