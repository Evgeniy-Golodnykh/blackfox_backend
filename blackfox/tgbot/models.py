from django.conf import settings
from django.db import models


class TelegramAccount(models.Model):
    """The Telegram account linked to a user — whom the bot may write to.

    A separate table, so the existing users table stays as it is.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='telegram',
        verbose_name='аккаунт',
    )
    telegram_id = models.BigIntegerField(
        unique=True,
        verbose_name='Telegram ID',
    )
    username = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name='имя в Telegram',
    )
    # False once the person blocks the bot: nothing is sent after that.
    can_write = models.BooleanField(
        default=True,
        verbose_name='бот может писать',
    )
    linked_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='привязан',
    )

    class Meta:
        verbose_name = 'Telegram-аккаунт'
        verbose_name_plural = 'Telegram-аккаунты'

    def __str__(self):
        return f'{self.user} ↔ {self.telegram_id}'
