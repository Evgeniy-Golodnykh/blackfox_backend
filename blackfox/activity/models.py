from django.conf import settings
from django.db import models


class ActivityDay(models.Model):
    """Calories burned in a day, as FatSecret has them — usually synced
    there from Apple Health / Google Fit (the whole day, rest included)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='activity_days',
        verbose_name='клиент',
    )
    date = models.DateField(verbose_name='день', db_index=True)
    calories_burned = models.PositiveIntegerField(
        verbose_name='потрачено, ккал',
    )
    synced_at = models.DateTimeField(auto_now=True, verbose_name='обновлено')

    class Meta:
        verbose_name = 'Активность за день'
        verbose_name_plural = 'Активность по дням'
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(fields=('user', 'date'),
                                    name='unique_activity_day'),
        ]

    def __str__(self):
        return f'{self.user}: {self.calories_burned} ккал за {self.date}'
