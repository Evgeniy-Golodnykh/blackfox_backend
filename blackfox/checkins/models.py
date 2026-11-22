from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

SCORE = [MinValueValidator(1), MaxValueValidator(5)]


class DailyCheckin(models.Model):
    """The client's morning check-in: four 1–5 scores and maybe a weight."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='checkins',
        verbose_name='клиент',
    )
    date = models.DateField(verbose_name='день', db_index=True)
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(30), MaxValueValidator(300)],
        verbose_name='вес, кг',
    )
    sleep = models.PositiveSmallIntegerField(validators=SCORE,
                                             verbose_name='сон')
    wellbeing = models.PositiveSmallIntegerField(validators=SCORE,
                                                 verbose_name='бодрость')
    stress = models.PositiveSmallIntegerField(validators=SCORE,
                                              verbose_name='стресс')
    hunger = models.PositiveSmallIntegerField(validators=SCORE,
                                              verbose_name='голод')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Чек-ин'
        verbose_name_plural = 'Чек-ины'
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=('user', 'date'),
                                    name='unique_daily_checkin'),
        ]

    def __str__(self):
        return f'Чек-ин {self.user} за {self.date}'
