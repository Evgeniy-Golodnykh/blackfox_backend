from django.contrib import admin

from tgbot.models import TelegramAccount


@admin.register(TelegramAccount)
class TelegramAccountAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'telegram_id', 'username', 'can_write', 'linked_at',
    )
    search_fields = ('user__email', 'user__username', 'username')
    raw_id_fields = ('user',)
