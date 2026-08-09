from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom User model."""

    class Gender(models.TextChoices):
        FEMALE = 'female'
        MALE = 'male'

    class Roles(models.TextChoices):
        ADMIN = 'admin'
        COACH = 'coach'
        USER = 'user'

    email = models.EmailField(
        max_length=254,
        unique=True,
        verbose_name='email',
    )
    image = models.ImageField(
        upload_to='user_images/',
        verbose_name='изображение',
        blank=True,
        null=True,
    )
    gender = models.CharField(
        max_length=6,
        choices=Gender.choices,
        default=None,
        verbose_name='пол',
    )
    role = models.CharField(
        max_length=5,
        choices=Roles.choices,
        default=Roles.USER,
        verbose_name='роль',
    )
    fatsecret_token = models.CharField(
        max_length=100,
        verbose_name='fatsecret_token',
        blank=True,
        null=True,
    )
    fatsecret_secret = models.CharField(
        max_length=100,
        verbose_name='fatsecret_secret',
        blank=True,
        null=True,
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['email']

    @property
    def is_admin(self):
        return self.role == self.Roles.ADMIN or self.is_superuser

    @property
    def is_coach(self):
        return self.role == self.Roles.COACH


class CoachProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        verbose_name='профиль тренера',
        related_name='coach_profile'
    )
    specialization = models.JSONField(default=list, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    education = models.JSONField(default=list, blank=True)
    bio = models.TextField(blank=True)
    price = models.CharField(max_length=100, blank=True)
    instagram = models.CharField(max_length=100, blank=True)
    telegram = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f'Профиль тренера: {self.user.get_full_name()}'
