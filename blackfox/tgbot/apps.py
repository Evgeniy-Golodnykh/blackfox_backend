from django.apps import AppConfig


class TgbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tgbot'
    verbose_name = 'Telegram'

    def ready(self):
        from tgbot import signals  # noqa: F401 — registers the receivers
