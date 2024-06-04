from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom User model."""

    class Roles(models.TextChoices):

        USER = 'user'
        COACH = 'coach'
        ADMIN = 'admin'

    email = models.EmailField(
        max_length=254,
        unique=True,
        verbose_name='email',
    )
    role = models.CharField(
        max_length=9,
        choices=Roles.choices,
        default=Roles.USER,
        verbose_name='role',
    )
    fatsecret_token = models.CharField(
        max_length=100,
        verbose_name='fatsecret_token',
    )
    fatsecret_secret = models.CharField(
        max_length=100,
        verbose_name='fatsecret_secret',
    )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['username']

    @property
    def is_admin(self):
        return self.role == self.Roles.ADMIN or self.is_superuser

    @property
    def is_coach(self):
        return self.role == self.Roles.COACH
