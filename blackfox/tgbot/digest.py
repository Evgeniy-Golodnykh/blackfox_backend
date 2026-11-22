"""What the bot says: the evening report, the Monday summary, reminders.

Plain text, no markup. The numbers follow the app (computeNormStreak in
src/features/stats/utils.ts), so the bot and the app never disagree.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Tuple

from checkins.models import DailyCheckin
from training.models import BodyStatsDiary, FoodDiary

MONTHS = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
          'августа', 'сентября', 'октября', 'ноября', 'декабря')

NBSP = ' '


@dataclass
class Message:
    kind: str
    text: str
    button: Optional[Tuple[str, str]] = None  # (text, app path)
    # For the picture version: a one-line caption (seen in the chat list)
    # and the date the card is for.
    caption: Optional[str] = None
    card_date: Optional[date] = None


def num(value):
    """1840 → «1 840» (no-break space, like the app)."""

    return f'{round(value):,}'.replace(',', NBSP)


def kg(value):
    return f'{value:.1f}'.replace('.', ',')


def day_month(date):
    return f'{date.day} {MONTHS[date.month - 1]}'


def has_food(entry):
    return entry is not None and entry.calories_actual > 0


def in_norm(entry):
    """Calories at most the target and protein at least the target; a
    missing (0) target doesn't count against the day."""

    calories_ok = (not entry.calories_target
                   or entry.calories_actual <= entry.calories_target)
    protein_ok = (not entry.protein_target
                  or entry.protein_actual >= entry.protein_target)
    return calories_ok and protein_ok


def diary_by_date(user, since, until):
    return {
        entry.date: entry
        for entry in FoodDiary.objects.filter(
            user=user, date__gte=since, date__lte=until,
        )
    }


def norm_streak(user, until):
    """Days in a row in the norm, ending on `until` (inclusive). A day with
    no food logged, or out of the norm, ends it."""

    diary = diary_by_date(user, until - timedelta(days=120), until)
    streak, day = 0, until
    while has_food(diary.get(day)) and in_norm(diary[day]):
        streak += 1
        day -= timedelta(days=1)
    return streak


def days_word(n):
    if n % 10 == 1 and n % 100 != 11:
        return 'день'
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return 'дня'
    return 'дней'


# ----- evening report ------------------------------------------------------

def daily_report(user, date):
    """The day's numbers against the plan, or None if nothing was logged."""

    entry = FoodDiary.objects.filter(user=user, date=date).first()
    if not has_food(entry):
        return None

    lines = [f'📊 Отчёт за {day_month(date)}', '']
    calories = entry.calories_actual
    target = entry.calories_target
    caption = f'📊 {day_month(date)} · {num(calories)}'
    if target:
        percent = round(calories / target * 100)
        lines.append(f'{num(calories)} / {num(target)} ккал · {percent}%')
    else:
        lines.append(f'{num(calories)} ккал')
    for label, actual, goal in (
        ('Белки', entry.protein_actual, entry.protein_target),
        ('Жиры', entry.fat_actual, entry.fat_target),
        ('Углеводы', entry.carbohydrate_actual, entry.carbohydrate_target),
        ('Клетчатка', entry.fiber_actual, entry.fiber_target),
    ):
        lines.append(f'{label} {num(actual)} / {num(goal)} г' if goal
                     else f'{label} {num(actual)} г')

    if target:
        lines.append('')
        diff = calories - target
        caption += f' / {num(target)} ккал · '
        if diff > target * 0.1:
            lines.append(f'⬆️ Больше нормы на {num(diff)} ккал')
            caption += f'⬆️ +{num(diff)}'
        elif diff < -target * 0.1:
            lines.append(f'⬇️ Меньше нормы на {num(-diff)} ккал')
            caption += f'⬇️ −{num(-diff)}'
        else:
            lines.append('✅ В пределах нормы')
            caption += '✅ в норме'
        protein_left = (entry.protein_target or 0) - entry.protein_actual
        if entry.protein_target and protein_left > entry.protein_target * 0.1:
            lines.append(f'🥩 Белка не хватило {num(protein_left)} г')
        streak = norm_streak(user, date)
        if streak >= 2:
            lines.append(f'🔥 {streak} {days_word(streak)} подряд в норме')
    else:
        caption += ' ккал'

    return Message(
        kind='daily_report',
        text='\n'.join(lines),
        button=('Открыть день', f'/stats?day={date.isoformat()}'),
        caption=caption,
        card_date=date,
    )


# ----- Monday summary ------------------------------------------------------

def weights_by_date(user, since, until):
    """FatSecret weigh-ins, filled in with check-in weights."""

    weights = {
        c.date: float(c.weight)
        for c in DailyCheckin.objects.filter(
            user=user, date__gte=since, date__lte=until, weight__isnull=False,
        )
    }
    for entry in FoodDiary.objects.filter(
        user=user, date__gte=since, date__lte=until, weight_actual__gt=0,
    ):
        weights[entry.date] = entry.weight_actual
    return weights


def average(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def weekly_report(user, monday):
    """The week before `monday` (Mon–Sun), or None if nothing was logged."""

    start, end = monday - timedelta(days=7), monday - timedelta(days=1)
    diary = diary_by_date(user, start, end)
    logged = [e for e in diary.values() if has_food(e)]
    if not logged:
        return None

    if start.month == end.month:
        period = f'{start.day}–{end.day} {MONTHS[end.month - 1]}'
    else:
        period = f'{day_month(start)} – {day_month(end)}'
    lines = [f'🗓 Неделя {period}', '',
             f'Записей: {len(logged)} из 7 дней']

    avg_calories = average(e.calories_actual for e in logged)
    targets = [e.calories_target for e in logged if e.calories_target]
    if targets:
        lines.append(f'Средние калории: {num(avg_calories)} / '
                     f'{num(average(targets))}')
        on_target = sum(
            1 for e in logged if e.calories_target
            and abs(e.calories_actual - e.calories_target)
            <= e.calories_target * 0.1
        )
        lines.append(f'Дней в норме (±10%): {on_target}')
    else:
        lines.append(f'Средние калории: {num(avg_calories)}')

    caption = f'🗓 Неделя {period}'
    weights = weights_by_date(user, start - timedelta(days=7), end)
    this_week = average(w for d, w in weights.items() if d >= start)
    last_week = average(w for d, w in weights.items() if d < start)
    if this_week is not None and last_week is not None:
        delta = round(this_week - last_week, 1)
        sign = '−' if delta < 0 else '+'
        lines.append(f'Вес: {kg(last_week)} → {kg(this_week)} кг '
                     f'({sign}{kg(abs(delta))})')
        caption += f' · вес {sign}{kg(abs(delta))} кг'
    elif this_week is not None:
        lines.append(f'Вес: {kg(this_week)} кг')

    return Message(kind='weekly_report', text='\n'.join(lines),
                   button=('Открыть статистику', '/stats'),
                   caption=caption, card_date=monday)


# ----- reminders -----------------------------------------------------------

def checkin_reminder(user, date):
    if DailyCheckin.objects.filter(user=user, date=date).exists():
        return None
    return Message(
        kind='checkin',
        text='Доброе утро! Чек-ин за 10 секунд: сон, бодрость, стресс, '
             'голод.',
        button=('Отметить', '/quick-add'),
    )


def evening_reminder(user, date):
    """At most one, most useful first: streak > food > weigh-in >
    measurements."""

    today = FoodDiary.objects.filter(user=user, date=date).first()
    if not has_food(today):
        return Message(
            kind='food',
            text='Еда за сегодня ещё не внесена — добавьте её в FatSecret, '
                 'и вечером пришлю отчёт.',
        )

    streak = norm_streak(user, date - timedelta(days=1))
    if streak >= 3 and not in_norm(today):
        protein_left = (today.protein_target or 0) - today.protein_actual
        over = today.calories_actual - (today.calories_target or 0)
        if today.calories_target and over > 0:
            hint = f'уже +{num(over)} ккал — на ужин что-то лёгкое'
        elif protein_left > 0:
            hint = f'осталось добрать {num(protein_left)} г белка'
        else:
            hint = 'чуть-чуть до нормы'
        return Message(
            kind='streak',
            text=f'Серия {streak} {days_word(streak)} в норме — не '
                 f'прерывайте: {hint}.',
            button=('Открыть день', f'/stats?day={date.isoformat()}'),
        )

    week_ago = date - timedelta(days=7)
    if not weights_by_date(user, week_ago, date):
        return Message(
            kind='weigh_in',
            text='Неделю нет взвешиваний. Завтра утром взвесьтесь натощак — '
                 'так видно настоящую динамику.',
            button=('Внести вес', '/quick-add'),
        )

    last = BodyStatsDiary.objects.filter(user=user).order_by('-date').first()
    if last is None or (date - last.date).days >= 14:
        return Message(
            kind='measurements',
            text='Пора обновить замеры: талия, живот, бёдра — раз в две '
                 'недели видно, как меняется фигура.',
            button=('Внести замеры', '/quick-add'),
        )
    return None


REMINDER_KINDS = ('food', 'streak', 'weigh_in', 'measurements')
