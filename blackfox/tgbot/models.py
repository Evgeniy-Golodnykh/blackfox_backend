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


class NotificationSettings(models.Model):
    """What the bot sends a user and when. One row per user, created with
    the defaults on first read."""

    CHECKIN_TIMES = ('07:00', '08:00', '09:00', '10:00')
    REPORT_TIMES = ('20:00', '21:00', '22:00')

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_settings',
        verbose_name='аккаунт',
    )
    daily_report = models.BooleanField(default=True,
                                       verbose_name='отчёт за день')
    weekly_report = models.BooleanField(default=True,
                                        verbose_name='итоги недели')
    checkin_reminder = models.BooleanField(default=True,
                                           verbose_name='утренний чек-ин')
    reminders = models.BooleanField(default=True,
                                    verbose_name='мягкие напоминания')
    checkin_time = models.CharField(
        max_length=5,
        choices=[(t, t) for t in CHECKIN_TIMES],
        default='08:00',
        verbose_name='время чек-ина',
    )
    report_time = models.CharField(
        max_length=5,
        choices=[(t, t) for t in REPORT_TIMES],
        default='21:00',
        verbose_name='время отчёта',
    )
    timezone = models.CharField(
        max_length=64,
        default='Europe/Moscow',
        verbose_name='часовой пояс',
    )
    updated_at = models.DateTimeField(auto_now=True)

    FLAGS = ('daily_report', 'weekly_report', 'checkin_reminder', 'reminders')

    class Meta:
        verbose_name = 'Настройки уведомлений'
        verbose_name_plural = 'Настройки уведомлений'

    def __str__(self):
        return f'Уведомления {self.user}'


class NotificationLog(models.Model):
    """One row per message the bot sent: (user, kind, date) is unique, and
    the row is written before sending, so nothing goes out twice."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='telegram_notifications',
        verbose_name='аккаунт',
    )
    kind = models.CharField(max_length=20, verbose_name='что')
    # The user's local day it's for (the Monday, for the weekly summary).
    date = models.DateField(verbose_name='за день')
    sent_at = models.DateTimeField(auto_now_add=True, verbose_name='когда')

    class Meta:
        verbose_name = 'Отправленное сообщение'
        verbose_name_plural = 'Отправленные сообщения'
        ordering = ['-sent_at']
        constraints = [
            models.UniqueConstraint(fields=('user', 'kind', 'date'),
                                    name='unique_telegram_notification'),
        ]

    def __str__(self):
        return f'{self.kind} → {self.user} за {self.date}'
