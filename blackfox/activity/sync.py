"""Pull calories burned per day from FatSecret's exercise diary
(exercise_entries.get_month.v2 — one call per month)."""

import logging
from datetime import date, timedelta

from django.core.cache import cache
from django.utils import timezone

from activity.models import ActivityDay

logger = logging.getLogger(__name__)

METHOD = 'exercise_entries.get_month.v2'
FRESH_FOR = timedelta(minutes=30)
EPOCH = date(1970, 1, 1)


def has_fatsecret(user):
    return bool(user.fatsecret_token and user.fatsecret_secret)


def month_days(session, base_url, day):
    """{date: kcal} for the month of `day`; days with nothing are absent."""

    data = session.get(base_url, params={
        'method': METHOD, 'format': 'json', 'date': (day - EPOCH).days,
    }).json()
    if data.get('error'):
        raise RuntimeError(f"FatSecret error {data['error'].get('code')}")
    days = (data.get('month') or {}).get('day') or []
    if isinstance(days, dict):  # a lone day comes bare
        days = [days]
    result = {}
    for item in days:
        try:
            result[EPOCH + timedelta(days=int(item['date_int']))] = round(
                float(item['calories']))
        except (KeyError, TypeError, ValueError):
            continue
    return result


def sync_activity(user, today=None):
    """This month and the last one into ActivityDay. Returns how many days
    were saved; 0 if FatSecret isn't linked or doesn't answer."""

    if not has_fatsecret(user):
        return 0
    from fatsecret.tools import BASE_URL, fatsecret

    today = today or timezone.localdate()
    try:
        session = fatsecret.get_session(
            token=(user.fatsecret_token, user.fatsecret_secret),
        )
        try:
            burned = {}
            for day in (today.replace(day=1) - timedelta(days=1), today):
                burned.update(month_days(session, BASE_URL, day))
        finally:
            session.close()
    except Exception as err:
        logger.warning('FatSecret activity for %s failed: %s', user.pk,
                       type(err).__name__)
        return 0
    for day, kcal in burned.items():
        if day <= today and kcal > 0:
            ActivityDay.objects.update_or_create(
                user=user, date=day, defaults={'calories_burned': kcal},
            )
    return len(burned)


def sync_if_stale(user):
    """At most every 30 minutes per user — the app asks often, and a user
    without Apple Health in FatSecret would otherwise be asked every time."""

    key = f'activity-sync-{user.pk}'
    if cache.get(key):
        return
    cache.set(key, True, FRESH_FOR.total_seconds())
    sync_activity(user)
