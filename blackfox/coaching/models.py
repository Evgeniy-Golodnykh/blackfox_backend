import secrets

from django.conf import settings
from django.db import models

CODE_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'  # no 0/o, 1/l/i


def new_code():
    return ''.join(secrets.choice(CODE_ALPHABET) for _ in range(10))


class CoachInvite(models.Model):
    """A coach's personal invite link: …/join/<code>. One per coach; a new
    code makes the old link stop working."""

    coach = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coach_invite',
        verbose_name='тренер',
    )
    code = models.CharField(max_length=16, unique=True, default=new_code,
                            verbose_name='код')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ссылка-приглашение тренера'
        verbose_name_plural = 'Ссылки-приглашения тренеров'

    def __str__(self):
        return f'{self.coach} — {self.code}'


class CoachClient(models.Model):
    """A client who is with a coach before (and alongside) the project:
    joined by the coach's link, or put there by an admin. The project, once
    there, stays the source of truth for the plan."""

    class Source(models.TextChoices):
        INVITE = 'invite', 'По ссылке тренера'
        ADMIN = 'admin', 'Назначил админ'

    client = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coach_link',
        verbose_name='клиент',
    )
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coach_clients',
        verbose_name='тренер',
    )
    source = models.CharField(max_length=10, choices=Source.choices,
                              default=Source.INVITE, verbose_name='откуда')
    joined_at = models.DateTimeField(auto_now_add=True,
                                     verbose_name='с какого момента')

    class Meta:
        verbose_name = 'Клиент тренера'
        verbose_name_plural = 'Клиенты тренеров'
        ordering = ['-joined_at']

    def __str__(self):
        return f'{self.client} → {self.coach}'


class NewClientNotice(models.Model):
    """The admin was told about a client who signed up without a
    questionnaire and without a coach — once per client."""

    client = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='new_client_notice',
        verbose_name='клиент',
    )
    sent_at = models.DateTimeField(auto_now_add=True,
                                   verbose_name='отправлено')

    class Meta:
        verbose_name = 'Уведомление о новом клиенте'
        verbose_name_plural = 'Уведомления о новых клиентах'

    def __str__(self):
        return f'{self.client} — {self.sent_at:%d.%m.%Y}'


class DayComment(models.Model):
    """The coach's word on one day of a client — shown in the app and sent
    with that day's evening report. Kept two weeks, then deleted."""

    client = models.ForeignKey(settings.AUTH_USER_MODEL,
                               on_delete=models.CASCADE,
                               related_name='day_comments',
                               verbose_name='клиент')
    coach = models.ForeignKey(settings.AUTH_USER_MODEL,
                              on_delete=models.SET_NULL, null=True,
                              related_name='day_comments_written',
                              verbose_name='тренер')
    date = models.DateField(verbose_name='день')
    text = models.TextField(max_length=1000, verbose_name='комментарий')
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name='создан')
    updated_at = models.DateTimeField(auto_now=True,
                                      verbose_name='изменён')
    # Sent to the client on its own (not inside the evening report).
    sent_at = models.DateTimeField(null=True, blank=True,
                                   verbose_name='отправлен отдельно')

    class Meta:
        verbose_name = 'Комментарий к дню'
        verbose_name_plural = 'Комментарии к дням'
        ordering = ['-date']
        constraints = [models.UniqueConstraint(
            fields=['client', 'date'], name='unique_day_comment')]

    def __str__(self):
        return f'{self.client} {self.date:%d.%m.%Y}'
