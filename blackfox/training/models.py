from django.contrib.auth import get_user_model
from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


User = get_user_model()


class Diet(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name='спортсмен',
    )
    url = models.URLField(
        verbose_name='ссылка на питание',
    )
    diet_date = models.DateField(
        verbose_name='дата питания',
        db_index=True
    )
    calories = models.FloatField(
        default=0,
        verbose_name='калории',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    calories_rdr = models.FloatField(
        default=0,
        verbose_name='рсп калории',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    calories_perc = models.FloatField(
        default=0,
        verbose_name='% калории',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    protein = models.FloatField(
        default=0,
        verbose_name='белки',
        validators=[MinValueValidator(0), MaxValueValidator(500)]
    )
    protein_rdr = models.FloatField(
        default=0,
        verbose_name='рсп белки',
        validators=[MinValueValidator(0), MaxValueValidator(500)]
    )
    protein_perc = models.FloatField(
        default=0,
        verbose_name='% белки',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    fat = models.FloatField(
        default=0,
        verbose_name='жиры',
        validators=[MinValueValidator(0), MaxValueValidator(500)]
    )
    fat_rdr = models.FloatField(
        default=0,
        verbose_name='рсп жиры',
        validators=[MinValueValidator(0), MaxValueValidator(500)]
    )
    fat_perc = models.FloatField(
        default=0,
        verbose_name='% жиры',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    carb = models.FloatField(
        default=0,
        verbose_name='углеводы',
        validators=[MinValueValidator(0), MaxValueValidator(500)]
    )
    carb_rdr = models.FloatField(
        default=0,
        verbose_name='рсп углеводы',
        validators=[MinValueValidator(0), MaxValueValidator(500)]
    )
    carb_perc = models.FloatField(
        default=0,
        verbose_name='% углеводы',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    fiber = models.FloatField(
        default=0,
        verbose_name='клетчатка',
        validators=[MinValueValidator(0), MaxValueValidator(200)]
    )
    fiber_rdr = models.FloatField(
        default=0,
        verbose_name='рсп клетчатка',
        validators=[MinValueValidator(0), MaxValueValidator(200)]
    )
    fiber_perc = models.FloatField(
        default=0,
        verbose_name='% клетчатка',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    water = models.FloatField(
        default=0,
        verbose_name='вода',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    water_rdr = models.FloatField(
        default=0,
        verbose_name='рсп вода',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    water_perc = models.FloatField(
        default=0,
        verbose_name='% вода',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    vitamin_d = models.FloatField(
        default=0,
        verbose_name='витамин Д',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    vitamin_d_rdr = models.FloatField(
        default=0,
        verbose_name='рсп витамин Д',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    vitamin_d_perc = models.FloatField(
        default=0,
        verbose_name='% витамин Д',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    potassium = models.FloatField(
        default=0,
        verbose_name='калий',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    potassium_rdr = models.FloatField(
        default=0,
        verbose_name='рсп калий',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    potassium_perc = models.FloatField(
        default=0,
        verbose_name='% калий',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    calcium = models.FloatField(
        default=0,
        verbose_name='кальций',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    calcium_rdr = models.FloatField(
        default=0,
        verbose_name='рсп кальций',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    calcium_perc = models.FloatField(
        default=0,
        verbose_name='% кальций',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    natrium = models.FloatField(
        default=0,
        verbose_name='натрий',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    natrium_rdr = models.FloatField(
        default=0,
        verbose_name='рсп натрий',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    natrium_perc = models.FloatField(
        default=0,
        verbose_name='% натрий',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    ferrum = models.FloatField(
        default=0,
        verbose_name='железо',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    ferrum_rdr = models.FloatField(
        default=0,
        verbose_name='рсп железо',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    ferrum_perc = models.FloatField(
        default=0,
        verbose_name='% железо',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    cholesterin = models.FloatField(
        default=0,
        verbose_name='холистерин',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    cholesterin_rdr = models.FloatField(
        default=0,
        verbose_name='рсп холистерин',
        validators=[MinValueValidator(0), MaxValueValidator(5000)]
    )
    cholesterin_perc = models.FloatField(
        default=0,
        verbose_name='% холистерин',
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        ordering = ['diet_date']

    def __str__(self):
        return self.calories
