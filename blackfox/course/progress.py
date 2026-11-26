"""Who sees which lesson: lesson N opens on day N from the start, in the
client's own time zone (the bot's settings), one a day."""

from datetime import timedelta

from django.utils import timezone

from course.models import Enrollment, Lesson, LessonRead

# Signed up this recently: the course starts by itself on the first visit.
AUTO_START_DAYS = 3


def local_today(user):
    """Today in the client's time zone (from the bot settings), so the
    app and the morning message agree on which lesson is open."""

    import pytz

    from tgbot.models import NotificationSettings

    prefs = NotificationSettings.objects.filter(user=user).first()
    try:
        zone = pytz.timezone(getattr(prefs, 'timezone', None)
                             or 'Europe/Moscow')
    except pytz.UnknownTimeZoneError:
        zone = pytz.timezone('Europe/Moscow')
    return timezone.now().astimezone(zone).date()


def current_day(enrollment, today):
    return (today - enrollment.started_on).days + 1


def published():
    return Lesson.objects.filter(is_published=True).order_by('day')


def enrollment_for(user, start=False):
    """The client's enrollment; a new client (signed up within 3 days) is
    enrolled on the first visit, anyone else — when they press «Начать»."""

    enrollment = Enrollment.objects.filter(user=user).first()
    if enrollment is not None or user.role != user.Roles.USER:
        return enrollment
    joined_recently = (timezone.now() - user.date_joined
                       <= timedelta(days=AUTO_START_DAYS))
    if start or joined_recently:
        enrollment, _ = Enrollment.objects.get_or_create(
            user=user, defaults={'started_on': local_today(user)})
    return enrollment


def overview(user, enrollment):
    lessons = list(published())
    read = set(LessonRead.objects.filter(user=user)
               .values_list('lesson__day', flat=True))
    today_day = (current_day(enrollment, local_today(user))
                 if enrollment else 0)
    return {
        'enrolled': enrollment is not None,
        'started_on': (enrollment.started_on.isoformat()
                       if enrollment else None),
        'day': min(today_day, len(lessons)) if enrollment else 0,
        'bot_lessons': enrollment.bot_lessons if enrollment else False,
        'read': len(read & {lesson.day for lesson in lessons}),
        'total': len(lessons),
        'lessons': [{
            'day': lesson.day,
            'title': lesson.title,
            'summary': lesson.summary,
            'unlocked': bool(enrollment) and lesson.day <= today_day,
            'read': lesson.day in read,
        } for lesson in lessons],
    }


def progress_of(user):
    """For the coach: (read, total), or None if not on the course."""

    if not Enrollment.objects.filter(user=user).exists():
        return None
    total = published().count()
    read = LessonRead.objects.filter(user=user,
                                     lesson__is_published=True).count()
    return read, total
