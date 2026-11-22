from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from activity.models import ActivityDay
from activity.sync import has_fatsecret, sync_if_stale
from checkins.views import can_read, not_your_client_message

User = get_user_model()

HISTORY_DAYS = 120


class ActivityView(APIView):
    """GET /api/activity/?user=<username> — calories burned per day (last
    120 days, newest first), freshly pulled from FatSecret if stale.

    {"fatsecret": true, "days": [{"date": "2026-11-22",
     "calories_burned": 2335}, …]}"""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        username = request.query_params.get('user') or request.user.username
        if not can_read(request.user, username):
            return Response({'detail': not_your_client_message},
                            status=status.HTTP_403_FORBIDDEN)
        user = User.objects.filter(username=username).first()
        if user is None:
            return Response({'fatsecret': False, 'days': []})
        sync_if_stale(user)
        since = timezone.localdate() - timedelta(days=HISTORY_DAYS)
        days = ActivityDay.objects.filter(user=user, date__gte=since)
        return Response({
            'fatsecret': has_fatsecret(user),
            'days': [{'date': d.date.isoformat(),
                      'calories_burned': d.calories_burned} for d in days],
        })
