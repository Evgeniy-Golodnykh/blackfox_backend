"""The admin's nudge when a calendar program is about to run out of
written workouts: once a day, while fewer than ALERT_DAYS remain."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

ALERT_DAYS = 5


def alert_schedule_gaps(today=None):
    from programs.models import ProgramSchedule
    from tgbot.telegram_api import SENT, send_message

    chat_id = settings.TELEGRAM_NOTIFY_CHAT_ID
    if not chat_id:
        return 0
    today = today or timezone.localdate()
    sent = 0
    for schedule in (ProgramSchedule.objects.select_related('program')
                     .filter(mode=ProgramSchedule.Mode.CALENDAR,
                             starts_on__isnull=False,
                             program__is_published=True)):
        if schedule.gap_alerted_on == today:
            continue
        last = schedule.program.days.order_by('-day').first()
        until = (schedule.starts_on + timedelta(days=last.day - 1)
                 if last else None)
        if until is not None and until >= today + timedelta(
                days=ALERT_DAYS):
            continue
        program = schedule.program
        text = (f'⚠️ {program.title}: тренировки расписаны до '
                f'{until:%d.%m} (день {last.day}).'
                if until else f'⚠️ {program.title}: тренировок нет.')
        text += (' Допишите следующий блок в редакторе программы — иначе '
                 'клиентам нечего будет открыть.')
        if send_message(chat_id, text) != SENT:
            continue
        schedule.gap_alerted_on = today
        schedule.save(update_fields=['gap_alerted_on'])
        sent += 1
    return sent
