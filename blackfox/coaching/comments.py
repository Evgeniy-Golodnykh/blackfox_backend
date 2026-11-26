"""The coach's comment on a client's day: kept 14 days, then deleted;
delivered with the day's evening report, or right away when that report
won't carry it."""

import logging
from datetime import timedelta

from django.utils import timezone

from coaching.models import DayComment

logger = logging.getLogger(__name__)

KEEP_DAYS = 14


def oldest_kept(today=None):
    return (today or timezone.localdate()) - timedelta(days=KEEP_DAYS - 1)


def purge_old(today=None):
    """Cron: delete comments older than two weeks. Returns how many."""

    deleted, _ = DayComment.objects.filter(
        date__lt=oldest_kept(today)).delete()
    return deleted


def comment_on(user, date):
    return DayComment.objects.filter(client=user, date=date).first()


def coach_name(comment):
    coach = comment.coach
    if coach is None:
        return 'Тренер'
    return (' '.join(p for p in (coach.first_name, coach.last_name) if p)
            or coach.username)


def report_will_carry(client, date):
    """True if today's evening report is still to come and will include
    the comment — then it isn't sent on its own."""

    from tgbot.models import NotificationLog, NotificationSettings
    from tgbot.scheduler import local_now_for

    prefs = NotificationSettings.objects.filter(user=client).first()
    if prefs is None or not prefs.daily_report:
        return False
    local_today = local_now_for(prefs, timezone.now()).date()
    if date != local_today:
        return False
    return not NotificationLog.objects.filter(
        user=client, kind='daily_report', date=date).exists()


def deliver_now(comment):
    """Send the comment to the client's chat unless the evening report
    will carry it; once per comment."""

    from tgbot import onboarding
    from tgbot.digest import day_month

    if comment.sent_at is not None:
        return
    if report_will_carry(comment.client, comment.date):
        return
    text = (f'💬 {coach_name(comment)} — к {day_month(comment.date)}:\n\n'
            f'{comment.text}')
    path = f'/stats?day={comment.date.isoformat()}'

    def build(_client):
        return text, onboarding.keyboard([onboarding.web_app('Открыть день',
                                                             path)])

    onboarding.send_later(comment.client, build)
    DayComment.objects.filter(pk=comment.pk).update(sent_at=timezone.now())
