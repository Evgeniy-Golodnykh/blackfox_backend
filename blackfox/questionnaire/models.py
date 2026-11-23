from django.conf import settings
from django.db import models


class Questionnaire(models.Model):
    """An application filled in on the landing page, before any account.

    The answers include health data (diagnoses, medication): never log them.
    """

    class Status(models.TextChoices):
        NEW = 'new', 'Новая'
        ACCEPTED = 'accepted', 'На ведении'
        DECLINED = 'declined', 'Отказ'

    version = models.PositiveSmallIntegerField(
        verbose_name='версия анкеты',
    )
    answers = models.JSONField(
        verbose_name='ответы',
    )
    consent_at = models.DateTimeField(
        verbose_name='время согласия',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='создана',
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.NEW,
        verbose_name='статус',
    )
    note = models.TextField(
        blank=True,
        default='',
        verbose_name='заметка',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='questionnaires',
        verbose_name='аккаунт',
    )
    # SHA-256 of the one-time token returned to the device that sent it;
    # the token itself is never stored. Emptied once claimed.
    claim_token_hash = models.CharField(
        max_length=64,
        blank=True,
        default='',
        db_index=True,
        verbose_name='хэш токена привязки',
    )
    claim_token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='токен привязки действует до',
    )

    class Meta:
        verbose_name = 'Анкета'
        verbose_name_plural = 'Анкеты'
        ordering = ['-created_at']

    def __str__(self):
        return f'Анкета №{self.pk}'


class ApplicationProgress(models.Model):
    """Where an application is on its way to a coach. A separate table, so
    the questionnaire table stays as it is; no row yet = «Новая».

    New → contacted → coach assigned → active (the coach made a plan), or
    declined / no answer (with a reason; archived after 30 days)."""

    class Stage(models.TextChoices):
        NEW = 'new', 'Новая'
        CONTACTED = 'contacted', 'Связались'
        ASSIGNED = 'assigned', 'Назначен тренер'
        ACTIVE = 'active', 'На ведении'
        DECLINED = 'declined', 'Отказ'
        NO_ANSWER = 'no_answer', 'Не отвечает'

    questionnaire = models.OneToOneField(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='progress',
        verbose_name='анкета',
    )
    stage = models.CharField(
        max_length=10,
        choices=Stage.choices,
        default=Stage.NEW,
        verbose_name='этап',
    )
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_applications',
        verbose_name='тренер',
    )
    reason = models.CharField(
        max_length=300,
        blank=True,
        default='',
        verbose_name='причина отказа',
    )
    stage_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='этап изменён',
    )
    # When each step was first reached — for the funnel; never cleared.
    first_response_at = models.DateTimeField(
        null=True, blank=True, verbose_name='первый ответ')
    assigned_at = models.DateTimeField(
        null=True, blank=True, verbose_name='тренер назначен')
    active_at = models.DateTimeField(
        null=True, blank=True, verbose_name='на ведении с')
    reminded_at = models.DateTimeField(
        null=True, blank=True, verbose_name='напоминание админу')
    # The sender's Telegram, when sent from the Mini App (checked initData).
    telegram_id = models.BigIntegerField(
        null=True, blank=True, verbose_name='Telegram отправителя')

    class Meta:
        verbose_name = 'Ход анкеты'
        verbose_name_plural = 'Ход анкет'

    def __str__(self):
        return f'Анкета №{self.questionnaire_id}: {self.get_stage_display()}'
