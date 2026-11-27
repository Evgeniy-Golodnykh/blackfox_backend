"""The morning workout in the bot: «Hyrox · день 4» with a button that
opens it in the app. Nothing on rest days, nothing once it's done, and
nothing for a day behind the subscription."""

from programs.access import current_day, day_state
from programs.models import ProgramDay, ProgramEnrollment, WorkoutLog


def workout_message(user, local_date):
    """Today's open, not yet logged workout of the user's programs (the
    most recently started first), or None."""

    from tgbot.digest import Message

    enrollments = (ProgramEnrollment.objects
                   .select_related('program', 'program__schedule')
                   .filter(user=user, program__is_published=True)
                   .order_by('-started_on'))
    for enrollment in enrollments:
        day = current_day(enrollment, local_date)
        row = ProgramDay.objects.filter(program=enrollment.program,
                                        day=day).first()
        if row is None or day_state(day, enrollment, local_date) != 'open':
            continue
        if WorkoutLog.objects.filter(user=user, day=row).exists():
            continue
        slug = enrollment.program.slug
        return Message(
            kind='workout',
            text=(f'🏋️ {enrollment.program.title} · день {day}\n'
                  f'{row.title}\n\n'
                  'Тренировка на сегодня ждёт в приложении. Выбери '
                  'вариант — лёгкий, базовый или сложный — и запиши '
                  'результат в дневник.'),
            button=('Открыть тренировку',
                    f'/more/online-programs/{slug}/{slug}/days/{day}'),
        )
    return None
