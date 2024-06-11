from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

User = get_user_model()


class FitnessDiary(models.Model):
    """FitnessDiary model for FatSecret data"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='спортсмен',
        related_name='diet',
    )
    date = models.DateField(
        verbose_name='дата питания',
        db_index=True
    )
    calories = models.PositiveIntegerField(
        default=0,
        verbose_name='калории',
        validators=[MinValueValidator(0), MaxValueValidator(10_000)]
    )
    carbohydrate = models.FloatField(
        default=0,
        verbose_name='углеводы',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    fat = models.FloatField(
        default=0,
        verbose_name='жиры',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    protein = models.FloatField(
        default=0,
        verbose_name='белки',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    weight = models.FloatField(
        verbose_name='вес',
        validators=[MinValueValidator(30), MaxValueValidator(250)]
    )

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'date'),
                name='unique_diets'
            )
        ]

    def __str__(self):
        return f'Дневник питания {self.user.username} за {self.date} г.'


class Project(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='спортсмен',
        related_name='project',
    )
    coach = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='тренер',
        related_name='coach',
    )
    start_date = models.DateField(
        verbose_name='начало проекта',
        db_index=True
    )
    deadline = models.DateField(
        verbose_name='окончание проекта',
        db_index=True
    )
    target_weight = models.FloatField(
        verbose_name='целевой вес',
        validators=[MinValueValidator(30), MaxValueValidator(250)]
    )
    is_closed = models.BooleanField(verbose_name='проект закрыт',
                                    default=False)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f'Цель {self.target_weight} кг. до {self.deadline} г.'
