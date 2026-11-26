"""The morning lesson in the bot: «День 3 из 14» with a button to read it."""

from course.models import Enrollment, Lesson, LessonRead
from course.progress import current_day


def lesson_message(user, local_date):
    """Today's lesson for this client, or None (not on the course, bot
    lessons off, finished, already read)."""

    from tgbot.digest import Message

    enrollment = Enrollment.objects.filter(user=user,
                                           bot_lessons=True).first()
    if enrollment is None:
        return None
    day = current_day(enrollment, local_date)
    lesson = Lesson.objects.filter(day=day, is_published=True).first()
    if lesson is None:
        return None
    if LessonRead.objects.filter(user=user, lesson=lesson).exists():
        return None
    total = Lesson.objects.filter(is_published=True).count()
    return Message(
        kind='lesson',
        text=(f'📘 Первые 14 дней · день {day} из {total}\n'
              f'{lesson.title}\n\n'
              f'{lesson.summary}\n\n'
              f'Действие на сегодня: {lesson.action}'),
        button=('Читать урок', f'/learn/{day}'),
    )
