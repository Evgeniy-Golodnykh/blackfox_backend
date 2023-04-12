from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

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
    confirmation_code = models.CharField(
        max_length=40,
        blank=True,
        verbose_name='confirmation_code',
    )

    class Meta:
        ordering = ['username']

    @property
    def is_admin(self):
        return self.role == self.Roles.ADMIN or self.is_superuser

    @property
    def is_coach(self):
        return self.role == self.Roles.COACH
