from django.conf import settings
from django.db import models


class CycleSettings(models.Model):
    """Cycle settings for a user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cycle_settings',
        verbose_name='пользователь',
    )
    cycle_length_days = models.PositiveSmallIntegerField(
        default=28,
        verbose_name='длина цикла в днях',
    )
    period_length_days = models.PositiveSmallIntegerField(
        default=5,
        verbose_name='длина менструации в днях',
    )

    def __str__(self):
        return f'Настройки цикла для {self.user.username}'


class PeriodEntry(models.Model):
    """Start date of a menstrual cycle."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='period_entries',
        verbose_name='пользователь',
    )
    date = models.DateField(
        verbose_name='дата начала цикла',
        db_index=True,
    )

    class Meta:
        ordering = ['-date']
        verbose_name = 'Period entry'
        verbose_name_plural = 'Period entries'

    def __str__(self):
        return f'{self.user.username}: {self.date}'


class PhaseOverride(models.Model):
    """Manual phase override for a specific date."""

    class Phase(models.TextChoices):
        MENSTRUAL = 'menstrual'
        FOLLICULAR = 'follicular'
        OVULATION = 'ovulation'
        LUTEAL = 'luteal'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='phase_overrides',
        verbose_name='пользователь',
    )
    date = models.DateField(
        verbose_name='дата',
        db_index=True,
    )
    phase = models.CharField(
        max_length=20,
        choices=Phase.choices,
        verbose_name='фаза',
    )

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'date'],
                name='unique_phase_override_user_date',
            ),
        ]
        verbose_name = 'Phase override'
        verbose_name_plural = 'Phase overrides'

    def __str__(self):
        return f'{self.user.username}: {self.date} - {self.phase}'
