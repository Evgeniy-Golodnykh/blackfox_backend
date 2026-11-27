"""Training programs sold in the app's shop: one program per direction,
a workout per training day with an easy, a base and a hard version, and
the client's diary. The plan opens day by day: day N on the N-th calendar
day from the start — the first week free, the rest while access is paid.
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class TrainingProgram(models.Model):
    slug = models.SlugField(
        max_length=40, unique=True, verbose_name='код',
        help_text='Тот же, что у программы в магазине приложения '
                  '(hyrox, crossfit, running, functional).')
    title = models.CharField(max_length=120, verbose_name='название')
    is_published = models.BooleanField(
        default=False, verbose_name='открыта',
        help_text='Пока не отмечено, программу нельзя начать.')

    class Meta:
        ordering = ['id']
        verbose_name = 'Программа'
        verbose_name_plural = 'Программы'

    def __str__(self):
        return self.title


TEXT_HELP = ('Абзацы — через пустую строку; строка с «• » — пункт '
             'списка; строка с «## » — подзаголовок.')


class ProgramDay(models.Model):
    """A training day. Calendar days without one are rest days."""

    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE,
                                related_name='days',
                                verbose_name='программа')
    day = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)], verbose_name='день',
        help_text='День от начала программы: 1, 2, 3… Дни без тренировки '
                  '— отдых.')
    title = models.CharField(max_length=120, verbose_name='тема дня')
    base = models.TextField(verbose_name='базовый вариант',
                            help_text=TEXT_HELP)
    easy = models.TextField(blank=True, default='',
                            verbose_name='лёгкий вариант',
                            help_text='Пусто — как базовый.')
    hard = models.TextField(blank=True, default='',
                            verbose_name='сложный вариант',
                            help_text='Пусто — как базовый.')

    class Meta:
        ordering = ['program', 'day']
        verbose_name = 'Тренировка'
        verbose_name_plural = 'Тренировки'
        constraints = [models.UniqueConstraint(
            fields=['program', 'day'], name='unique_program_day')]

    def __str__(self):
        return f'{self.program} · день {self.day}: {self.title}'


class ProgramEnrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='program_enrollments',
                             verbose_name='клиент')
    program = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE,
                                related_name='enrollments',
                                verbose_name='программа')
    started_on = models.DateField(verbose_name='начало')
    paid_until = models.DateField(
        null=True, blank=True, verbose_name='оплачено до',
        help_text='Включительно. Пусто — только бесплатная неделя.')

    class Meta:
        verbose_name = 'Участник программы'
        verbose_name_plural = 'Участники программ'
        constraints = [models.UniqueConstraint(
            fields=['user', 'program'], name='unique_program_enrollment')]

    def __str__(self):
        return f'{self.user} · {self.program} с {self.started_on:%d.%m.%Y}'


class WorkoutLog(models.Model):
    """The diary: one entry per training day."""

    class Level(models.TextChoices):
        EASY = 'easy', 'лёгкий'
        BASE = 'base', 'базовый'
        HARD = 'hard', 'сложный'

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name='workout_logs',
                             verbose_name='клиент')
    day = models.ForeignKey(ProgramDay, on_delete=models.CASCADE,
                            related_name='logs', verbose_name='тренировка')
    level = models.CharField(max_length=4, choices=Level.choices,
                             default=Level.BASE, verbose_name='вариант')
    done_on = models.DateField(verbose_name='дата')
    result = models.CharField(max_length=300, blank=True, default='',
                              verbose_name='результат',
                              help_text='Веса, время, раунды.')
    feel = models.PositiveSmallIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='самочувствие (1–5)')
    note = models.TextField(blank=True, default='', max_length=2000,
                            verbose_name='заметка')
    updated_at = models.DateTimeField(auto_now=True,
                                      verbose_name='изменено')

    class Meta:
        ordering = ['-done_on', '-id']
        verbose_name = 'Запись дневника'
        verbose_name_plural = 'Дневник тренировок'
        constraints = [models.UniqueConstraint(
            fields=['user', 'day'], name='unique_workout_log')]

    def __str__(self):
        return f'{self.user} · {self.day}'


class ProgramPrice(models.Model):
    """What 30 days of a program cost, set by the admin in the app (a
    table of its own, so the programs table stays as it is)."""

    program = models.OneToOneField(TrainingProgram,
                                   on_delete=models.CASCADE,
                                   related_name='price',
                                   verbose_name='программа')
    rubles = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='цена за 30 дней, ₽',
        help_text='Пусто — «Цена скоро».')
    updated_at = models.DateTimeField(auto_now=True,
                                      verbose_name='изменено')

    class Meta:
        verbose_name = 'Цена программы'
        verbose_name_plural = 'Цены программ'

    def __str__(self):
        return f'{self.program}: {self.rubles or "—"} ₽'


class ProgramSchedule(models.Model):
    """How a program runs (a table of its own, so the programs table stays
    as it is). «calendar» — one stream for everyone: day 1 is `starts_on`,
    today's workout is the same for all, a client joins at today's day.
    «personal» — each client starts at day 1 on the day they start."""

    class Mode(models.TextChoices):
        CALENDAR = 'calendar', 'сквозная (по календарю)'
        PERSONAL = 'personal', 'с первого дня'

    program = models.OneToOneField(TrainingProgram,
                                   on_delete=models.CASCADE,
                                   related_name='schedule',
                                   verbose_name='программа')
    mode = models.CharField(max_length=8, choices=Mode.choices,
                            default=Mode.CALENDAR, verbose_name='режим')
    starts_on = models.DateField(
        null=True, blank=True, verbose_name='день 1',
        help_text='Для сквозной программы: дата первого дня.')
    gap_alerted_on = models.DateField(
        null=True, blank=True, verbose_name='предупреждали о конце',
        help_text='Когда последний раз писали, что тренировки '
                  'заканчиваются.')

    class Meta:
        verbose_name = 'Расписание программы'
        verbose_name_plural = 'Расписания программ'

    def __str__(self):
        return f'{self.program}: {self.get_mode_display()}'
