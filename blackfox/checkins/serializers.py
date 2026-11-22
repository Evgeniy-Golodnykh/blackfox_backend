from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from checkins.models import DailyCheckin

MAX_AGE_DAYS = 7

error_future_message = 'Нельзя отметить день, который ещё не наступил.'
error_old_message = 'Отметить можно только последние 7 дней.'


class CheckinSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(slug_field='username', read_only=True)
    weight = serializers.FloatField(
        required=False, allow_null=True, min_value=30, max_value=300,
    )
    sleep = serializers.IntegerField(min_value=1, max_value=5)
    wellbeing = serializers.IntegerField(min_value=1, max_value=5)
    stress = serializers.IntegerField(min_value=1, max_value=5)
    hunger = serializers.IntegerField(min_value=1, max_value=5)

    class Meta:
        model = DailyCheckin
        fields = ('id', 'user', 'date', 'weight', 'sleep', 'wellbeing',
                  'stress', 'hunger')
        # The upsert in the view handles (user, date) itself.
        validators = []

    def validate_date(self, value):
        # The client's "today" may be a day ahead of the server's (time
        # zones east of Moscow) — allow that much.
        today = timezone.localdate()
        if value > today + timedelta(days=1):
            raise serializers.ValidationError(error_future_message)
        if value < today - timedelta(days=MAX_AGE_DAYS):
            raise serializers.ValidationError(error_old_message)
        return value

    def validate_weight(self, value):
        return None if value is None else round(value, 1)
