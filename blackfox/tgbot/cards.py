"""Data for the picture report (tgbot/card/card.html → window.renderCard).

The contract is in the app repo, docs/telegram-bot-reports.md («Картинка-
отчёт»). Every block is optional: missing data just isn't drawn.
"""

import logging
from datetime import timedelta

from tgbot.digest import diary_by_date, has_food, weights_by_date

logger = logging.getLogger(__name__)

MEAL_NAMES = (('Breakfast', 'Завтрак'), ('Lunch', 'Обед'),
              ('Dinner', 'Ужин'), ('Other', 'Перекус'))


def logging_streak(user, date):
    """Days in a row, ending on `date`, with food logged."""

    diary = diary_by_date(user, date - timedelta(days=120), date)
    streak, day = 0, date
    while has_food(diary.get(day)):
        streak += 1
        day -= timedelta(days=1)
    return streak


def average(values):
    values = list(values)
    return round(sum(values) / len(values), 1) if values else None


def weight_block(user, date):
    """Average of the 7 days to `date` vs the 7 before, and weekly
    averages for up to 5 weeks — as in the app, not single weigh-ins."""

    weights = weights_by_date(user, date - timedelta(days=34), date)
    if not weights:
        return None
    week_start = date - timedelta(days=6)
    avg = average(w for d, w in weights.items() if d >= week_start)
    prev = average(w for d, w in weights.items()
                   if week_start - timedelta(days=7) <= d < week_start)
    points = []
    for back in range(4, -1, -1):
        start = week_start - timedelta(days=7 * back)
        value = average(w for d, w in weights.items()
                        if start <= d < start + timedelta(days=7))
        if value is not None:
            points.append({'label': start.strftime('%d.%m'),
                           'weight': value})
    if avg is None:
        return None
    block = {'avg': avg, 'points': points}
    if prev is not None:
        block['prevAvg'] = prev
    return block


def meals_for(user, date):
    """Calories per meal from FatSecret (the diary keeps only day totals).
    Empty if FatSecret isn't linked or doesn't answer."""

    if not (user.fatsecret_token and user.fatsecret_secret):
        return []
    try:
        from fatsecret.tools import (
            PARAMS_FOOD_DAILY, fatsecret, get_fatsecret_data,
        )
        session = fatsecret.get_session(
            token=(user.fatsecret_token, user.fatsecret_secret),
        )
        try:
            day = get_fatsecret_data(session, dict(PARAMS_FOOD_DAILY), date)
        finally:
            session.close()
    except Exception as err:
        logger.warning('FatSecret meals for %s failed: %s', user.pk,
                       type(err).__name__)
        return []
    entries = (day or {}).get('food_entry') or []
    if isinstance(entries, dict):  # FatSecret sends a lone entry bare
        entries = [entries]
    totals = {}
    for entry in entries:
        try:
            calories = float(entry.get('calories', 0))
        except (TypeError, ValueError):
            continue
        totals[entry.get('meal')] = totals.get(entry.get('meal'), 0) + calories
    return [{'name': name, 'calories': round(totals[key])}
            for key, name in MEAL_NAMES if totals.get(key)]


def first_name(user):
    return (user.first_name or '').strip() or None


def day_card(user, date, with_meals=True):
    entry = diary_by_date(user, date, date).get(date)
    if not has_food(entry):
        return None
    target = {
        key: value for key, value in (
            ('calories', entry.calories_target),
            ('protein', entry.protein_target),
            ('fat', entry.fat_target),
            ('carbs', entry.carbohydrate_target),
            ('fiber', entry.fiber_target),
            ('sugar', entry.sugar_target),
        ) if value
    }
    week = diary_by_date(user, date - timedelta(days=6), date)
    data = {
        'kind': 'day',
        'date': date.isoformat(),
        'name': first_name(user),
        'calories': entry.calories_actual,
        'protein': round(entry.protein_actual),
        'fat': round(entry.fat_actual),
        'carbs': round(entry.carbohydrate_actual),
        'fiber': round(entry.fiber_actual),
        'sugar': round(entry.sugar_actual),
        'target': target,
        'streak': logging_streak(user, date),
        'meals': meals_for(user, date) if with_meals else [],
        'last7': [
            {'date': (date - timedelta(days=back)).isoformat(),
             'calories': getattr(week.get(date - timedelta(days=back)),
                                 'calories_actual', 0)}
            for back in range(6, -1, -1)
        ],
        'note': None,
    }
    weight = weight_block(user, date)
    if weight:
        data['weight'] = weight
    return data


def week_card(user, monday):
    start, end = monday - timedelta(days=7), monday - timedelta(days=1)
    diary = diary_by_date(user, start, end)
    if not any(has_food(e) for e in diary.values()):
        return None
    targets = [e.calories_target for e in diary.values()
               if has_food(e) and e.calories_target]
    data = {
        'kind': 'week',
        'from': start.isoformat(),
        'to': end.isoformat(),
        'name': first_name(user),
        'target': ({'calories': round(sum(targets) / len(targets))}
                   if targets else {}),
        'days': [
            {'date': (start + timedelta(days=i)).isoformat(),
             'calories': getattr(diary.get(start + timedelta(days=i)),
                                 'calories_actual', 0)}
            for i in range(7)
        ],
    }
    weight = weight_block(user, end)
    if weight:
        data['weight'] = weight
    return data
