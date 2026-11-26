"""The morning lesson in the bot: «День 3 из 14» with a button to read it."""

from course.models import Enrollment, Lesson, LessonRead
from course.progress import current_day

# After the last lesson's day, unread ones are still sent for a week.
CATCH_UP_DAYS = 7


def lesson_message(user, local_date):
    """The earliest lesson whose day has come and that isn't read yet, or
    None (not on the course, bot lessons off, everything due is read —
    also when they read ahead)."""

    from tgbot.digest import Message

    enrollment = Enrollment.objects.filter(user=user,
                                           bot_lessons=True).first()
    if enrollment is None:
        return None
    day = current_day(enrollment, local_date)
    total = Lesson.objects.filter(is_published=True).count()
    if day > total + CATCH_UP_DAYS:
        return None  # the course is long over — no more nudges
    read = LessonRead.objects.filter(user=user).values_list('lesson_id',
                                                            flat=True)
    lesson = (Lesson.objects.filter(is_published=True, day__lte=day)
              .exclude(pk__in=read).order_by('day').first())
    if lesson is None:
        return None
    return Message(
        kind='lesson',
        text=(f'📘 Первые 14 дней · урок {lesson.day} из {total}\n'
              f'{lesson.title}\n\n'
              f'{lesson.summary}\n\n'
              f'Действие на сегодня: {lesson.action}'),
        button=('Читать урок', f'/learn/{lesson.day}'),
    )
