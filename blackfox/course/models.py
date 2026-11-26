from django.conf import settings
from django.db import models


class Lesson(models.Model):
    """One day of «Первые 14 дней». Edited in the admin; the starting texts
    come from course/lessons_first14.py."""

    day = models.PositiveSmallIntegerField(unique=True, verbose_name='день')
    title = models.CharField(max_length=120, verbose_name='заголовок')
    summary = models.CharField(
        max_length=200, verbose_name='коротко',
        help_text='Одна строка — в сообщении бота и в списке уроков.')
    body = models.TextField(
        verbose_name='текст',
        help_text='Абзацы — через пустую строку; строка с «• » — пункт '
                  'списка.')
    action = models.CharField(max_length=300, verbose_name='действие дня')
    sources = models.TextField(blank=True, default='',
                               verbose_name='источники',
                               help_text='По одному на строку.')
    is_published = models.BooleanField(default=True,
                                       verbose_name='опубликован')

    class Meta:
        ordering = ['day']
        verbose_name = 'Урок'
        verbose_name_plural = 'Уроки'

    def __str__(self):
        return f'День {self.day}: {self.title}'


class Enrollment(models.Model):
    """A client on the course: lesson N opens on day N from the start."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name='course_enrollment',
                                verbose_name='клиент')
    started_on = models.DateField(verbose_name='начало')
    bot_lessons = models.BooleanField(default=True,
                                      verbose_name='уроки в боте')

    class Meta:
        verbose_name = 'Участник курса'
        verbose_name_plural = 'Участники курса'

    def __str__(self):
        return f'{self.user} с {self.started_on:%d.%m.%Y}'


class LessonRead(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='lessons_read',
                             verbose_name='клиент')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE,
                               related_name='reads', verbose_name='урок')
    read_at = models.DateTimeField(auto_now_add=True,
                                   verbose_name='прочитан')

    class Meta:
        verbose_name = 'Прочитанный урок'
        verbose_name_plural = 'Прочитанные уроки'
        constraints = [models.UniqueConstraint(
            fields=['user', 'lesson'], name='unique_lesson_read')]

    def __str__(self):
        return f'{self.user}: день {self.lesson.day}'
