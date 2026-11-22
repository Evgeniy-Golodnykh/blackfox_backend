"""Who gets what, now. Run every 10 minutes by cron (tgbot.cron).

For each client whose Telegram is linked and not blocked, in their own
time zone: the morning check-in nudge, the evening reminder (20:00), the
evening report (report_time) and the Monday summary (10:00). Each goes out
once: a NotificationLog row is written first, and a second run finds it.
"""

import logging
import time
from datetime import datetime, time as dtime, timedelta

import pytz
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from activity.sync import sync_activity
from tgbot import cards, digest
from tgbot.card_render import CardRenderer
from tgbot.models import NotificationLog, NotificationSettings
from tgbot.telegram_api import BLOCKED, FAILED, send_message, send_photo
from training.models import FoodDiary, Project

logger = logging.getLogger(__name__)
User = get_user_model()

EVENING_REMINDER_AT = dtime(20, 0)
WEEKLY_AT = dtime(10, 0)
# A slot missed by more than this (server down) is skipped, not sent at
# night.
LATE_LIMIT = timedelta(hours=3)
PAUSE_BETWEEN_SENDS = 0.05  # well under Telegram's ~30 messages/second


def parse_time(value):
    hours, minutes = value.split(':')
    return dtime(int(hours), int(minutes))


def is_due(local_now, slot):
    start = local_now.replace(hour=slot.hour, minute=slot.minute, second=0,
                              microsecond=0)
    return start <= local_now < start + LATE_LIMIT


def local_now_for(prefs, now):
    try:
        zone = pytz.timezone(prefs.timezone)
    except pytz.UnknownTimeZoneError:
        zone = pytz.timezone('Europe/Moscow')
    return now.astimezone(zone)


def refresh_diary(user):
    """Pull today's food from FatSecret, as the app does on opening. A
    failure leaves the diary as it was."""

    from fatsecret.tools import get_fooddiary_objects

    if not (user.fatsecret_token and user.fatsecret_secret):
        return
    try:
        with transaction.atomic():
            FoodDiary.objects.bulk_create(get_fooddiary_objects(user))
    except Exception as err:  # FatSecret down, token revoked…
        logger.warning('FatSecret refresh for %s failed: %s', user.pk,
                       type(err).__name__)
    sync_activity(user)  # calories burned, for the report's balance line


def due_messages(user, prefs, now, refresh=True):
    """[(Message, log date)] due for this user right now."""

    local = local_now_for(prefs, now)
    today = local.date()
    sent = set(NotificationLog.objects.filter(
        user=user, date__gte=today - timedelta(days=1),
    ).values_list('kind', 'date'))
    has_project = Project.objects.filter(user=user).exists()
    fatsecret = bool(user.fatsecret_token and user.fatsecret_secret)
    due = []

    if (prefs.checkin_reminder and ('checkin', today) not in sent
            and is_due(local, parse_time(prefs.checkin_time))):
        message = digest.checkin_reminder(user, today)
        if message:
            due.append((message, today))

    evening_report = (prefs.daily_report and ('daily_report', today)
                      not in sent and is_due(local,
                                             parse_time(prefs.report_time)))
    evening_reminder = (
        prefs.reminders and has_project and fatsecret
        and not any((kind, today) in sent for kind in digest.REMINDER_KINDS)
        and is_due(local, EVENING_REMINDER_AT)
    )
    if (evening_report or evening_reminder) and refresh and has_project:
        refresh_diary(user)
    if evening_reminder:
        message = digest.evening_reminder(user, today)
        if message:
            due.append((message, today))
    if evening_report:
        message = digest.daily_report(user, today)
        if message:
            due.append((message, today))

    if (prefs.weekly_report and local.weekday() == 0
            and ('weekly_report', today) not in sent
            and is_due(local, WEEKLY_AT)):
        message = digest.weekly_report(user, today)
        if message:
            due.append((message, today))
    return due


def card_data(user, message):
    if message.card_date is None:
        return None
    if message.kind == 'daily_report':
        return cards.day_card(user, message.card_date)
    return cards.week_card(user, message.card_date)


def send(account, message, renderer=None):
    """The picture with a caption when it can be drawn, else the text."""

    if renderer is not None and message.card_date is not None:
        data = card_data(account.user, message)
        jpeg = renderer.render(data) if data else None
        if jpeg:
            return send_photo(account.telegram_id, jpeg, message.caption,
                              message.button)
    return send_message(account.telegram_id, message.text, message.button)


def new_renderer():
    return CardRenderer() if settings.TELEGRAM_REPORT_CARDS else None


def deliver(account, message, log_date, renderer=None):
    """Write the log row, then send. 'skipped' if already sent."""

    try:
        with transaction.atomic():
            log = NotificationLog.objects.create(
                user=account.user, kind=message.kind, date=log_date,
            )
    except IntegrityError:
        return 'skipped'
    result = send(account, message, renderer)
    if result == BLOCKED:
        account.can_write = False
        account.save(update_fields=['can_write'])
        NotificationSettings.objects.update_or_create(
            user=account.user,
            defaults={flag: False for flag in NotificationSettings.FLAGS},
        )
    elif result == FAILED:
        log.delete()  # try again on the next run, while still in time
    return result


def recipients():
    return User.objects.filter(
        role=User.Roles.USER, is_active=True, telegram__can_write=True,
    ).select_related('telegram')


def run(now=None, dry_run=False, usernames=None, refresh=True):
    """Send everything that's due. dry_run: only return what would go."""

    now = now or timezone.now()
    users = recipients()
    if usernames:
        users = users.filter(username__in=usernames)
    report = []
    renderer = None if dry_run else new_renderer()
    try:
        for user in users:
            report.extend(run_for(user, now, dry_run, refresh, renderer))
    finally:
        if renderer is not None:
            renderer.close()
    return report


def run_for(user, now, dry_run, refresh, renderer):
    """[(username, Message, result)] for one user."""

    prefs = (NotificationSettings.objects.filter(user=user).first()
             or NotificationSettings(user=user))
    try:
        messages = due_messages(user, prefs, now, refresh=refresh)
    except Exception as err:
        logger.exception('Telegram schedule for %s failed: %s', user.pk,
                         type(err).__name__)
        return []
    report = []
    for message, log_date in messages:
        if dry_run:
            report.append((user.username, message, 'dry-run'))
            continue
        result = deliver(user.telegram, message, log_date, renderer)
        report.append((user.username, message, result))
        time.sleep(PAUSE_BETWEEN_SENDS)
    return report


def send_now(user, kind, now=None):
    """Send one message to the user right away, ignoring the time and the
    log — the «Прислать пример» button in the app. None if there's nothing
    to say yet (e.g. no food logged)."""

    now = now or timezone.now()
    prefs = (NotificationSettings.objects.filter(user=user).first()
             or NotificationSettings(user=user))
    today = local_now_for(prefs, now).date()
    if kind == 'daily_report':
        refresh_diary(user)
        last = FoodDiary.objects.filter(
            user=user, date__lte=today, calories_actual__gt=0,
        ).order_by('-date').first()
        message = digest.daily_report(user, last.date) if last else None
    elif kind == 'weekly_report':
        monday = today - timedelta(days=today.weekday())
        message = digest.weekly_report(user, monday)
    else:
        message = digest.Message(
            kind='checkin',
            text='Доброе утро! Чек-ин за 10 секунд: сон, бодрость, стресс, '
                 'голод.',
            button=('Отметить', '/quick-add'),
        )
    if message is None:
        return None
    renderer = new_renderer()
    try:
        return send(user.telegram, message, renderer)
    finally:
        if renderer is not None:
            renderer.close()


def as_local(naive, zone='Europe/Moscow'):
    """For the command: «2026-11-23 21:05» in a zone → aware datetime."""

    return pytz.timezone(zone).localize(
        datetime.strptime(naive, '%Y-%m-%d %H:%M'),
    )
