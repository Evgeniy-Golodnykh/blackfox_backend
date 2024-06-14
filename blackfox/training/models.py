from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

User = get_user_model()


class FoodDiary(models.Model):
    """FoodDiary model for FatSecret data"""

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
    calories_actual = models.PositiveIntegerField(
        verbose_name='калории факт',
        validators=[MinValueValidator(0), MaxValueValidator(10_000)]
    )
    calories_target = models.PositiveIntegerField(
        verbose_name='калории план',
        validators=[MinValueValidator(0), MaxValueValidator(10_000)]
    )
    carbohydrate_actual = models.FloatField(
        verbose_name='углеводы факт',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    carbohydrate_target = models.FloatField(
        verbose_name='углеводы план',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    fat_actual = models.FloatField(
        verbose_name='жиры факт',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    fat_target = models.FloatField(
        verbose_name='жиры план',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    fiber_actual = models.FloatField(
        verbose_name='пищевые волокна факт',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    fiber_target = models.FloatField(
        verbose_name='пищевые волокна план',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    protein_actual = models.FloatField(
        verbose_name='белки факт',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    protein_target = models.FloatField(
        verbose_name='белки план',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    sugar_actual = models.FloatField(
        verbose_name='сахар факт',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )
    sugar_target = models.FloatField(
        verbose_name='сахар план',
        validators=[MinValueValidator(0), MaxValueValidator(1_000)]
    )

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'date'),
                name='unique_food_diary'
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
    is_closed = models.BooleanField(
        verbose_name='проект закрыт',
        default=False
    )

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f'Цель {self.target_weight} кг. до {self.deadline} г.'
