import pytz
from rest_framework import serializers

from tgbot.models import NotificationSettings, TelegramAccount

error_timezone_message = 'Неизвестный часовой пояс.'


class NotificationSettingsSerializer(serializers.ModelSerializer):
    telegram_linked = serializers.SerializerMethodField()

    class Meta:
        model = NotificationSettings
        fields = (
            'telegram_linked', 'daily_report', 'weekly_report',
            'checkin_reminder', 'reminders', 'checkin_time', 'report_time',
            'timezone',
        )

    def get_telegram_linked(self, obj):
        """Linked and the bot may still write (not blocked)."""

        return TelegramAccount.objects.filter(
            user=obj.user, can_write=True,
        ).exists()

    def validate_timezone(self, value):
        if value not in pytz.all_timezones_set:
            raise serializers.ValidationError(error_timezone_message)
        return value
