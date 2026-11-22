from django.contrib import admin

from tgbot.models import NotificationSettings, TelegramAccount


@admin.register(TelegramAccount)
class TelegramAccountAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'telegram_id', 'username', 'can_write', 'linked_at',
    )
    search_fields = ('user__email', 'user__username', 'username')
    raw_id_fields = ('user',)


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'daily_report', 'weekly_report', 'checkin_reminder',
        'reminders', 'checkin_time', 'report_time', 'timezone',
    )
    raw_id_fields = ('user',)
