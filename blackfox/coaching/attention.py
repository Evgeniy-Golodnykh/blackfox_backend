"""«Нужно внимание»: which of a coach's clients need a word today, and why.

Each rule is a reason with a plain-language text; a client with several
comes first. The coach decides what to do — nothing here messages the
client.
"""

from datetime import timedelta

from django.utils import timezone

NO_FOOD_DAYS = 3
OVER_DAYS = 3
OVER_SHARE = 1.10          # more than 10 % above the calories target
STALL_DAYS = 14
STALL_KG = 0.2
NO_WEIGHT_DAYS = 7
WAITING_HOURS = 24

# severity: 2 — act today, 1 — keep an eye on it
URGENT, WATCH = 2, 1


def reason(kind, text, severity):
    return {'kind': kind, 'text': text, 'severity': severity}


def food_reasons(user, project, today):
    from tgbot.digest import diary_by_date, has_food

    if project is None or not (user.fatsecret_token and user.fatsecret_secret):
        return []
    # Days since the plan started count; before that there's nothing to
    # expect.
    since = max(project.start_date, today - timedelta(days=13))
    diary = diary_by_date(user, since, today)
    reasons = []
    recent = [today - timedelta(days=i) for i in range(1, NO_FOOD_DAYS + 1)]
    if all(day >= project.start_date for day in recent) and not any(
            has_food(diary.get(day)) for day in recent):
        reasons.append(reason('no_food', 'Не вносит еду 3 дня', URGENT))
    over = [diary.get(day) for day in recent]
    if all(has_food(e) and e.calories_target
           and e.calories_actual > e.calories_target * OVER_SHARE
           for e in over):
        reasons.append(reason('over', 'Перебор калорий 3 дня подряд',
                              URGENT))
    return reasons


def average(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def weight_reasons(user, project, today):
    from tgbot.digest import weights_by_date

    if project is None:
        return []
    weights = weights_by_date(user, today - timedelta(days=STALL_DAYS + 7),
                              today)
    if not weights:
        if (today - project.start_date).days >= NO_WEIGHT_DAYS:
            return [reason('no_weight', 'Нет взвешиваний', WATCH)]
        return []
    last = max(weights)
    if (today - last).days >= NO_WEIGHT_DAYS:
        return [reason('no_weight',
                       f'Не взвешивался {(today - last).days} дн.', WATCH)]
    # The plan's direction: losing unless the target is above the start.
    losing = (project.target_weight or 0) <= (project.start_weight or 0)
    now_week = [w for d, w in weights.items() if d > today - timedelta(7)]
    then_week = [w for d, w in weights.items()
                 if today - timedelta(STALL_DAYS + 7) < d
                 <= today - timedelta(STALL_DAYS)]
    if len(now_week) >= 2 and len(then_week) >= 2:
        change = average(now_week) - average(then_week)
        stalled = (change > -STALL_KG) if losing else (change < STALL_KG)
        if stalled and (today - project.start_date).days >= STALL_DAYS + 7:
            return [reason('stall', 'Вес стоит 2 недели', WATCH)]
    return []


def checkin_reasons(user, today):
    from checkins.models import DailyCheckin

    recent = list(DailyCheckin.objects.filter(
        user=user, date__gt=today - timedelta(days=4)).order_by('-date')[:3])
    if len(recent) < 2:
        return []
    reasons = []
    if average(c.sleep for c in recent) <= 2:
        reasons.append(reason('sleep', 'Плохой сон в чек-инах', WATCH))
    if sum(c.stress >= 4 for c in recent) >= 2:
        reasons.append(reason('stress', 'Высокий стресс в чек-инах', WATCH))
    if sum(c.hunger >= 4 for c in recent) >= 2:
        reasons.append(reason('hunger', 'Сильный голод в чек-инах', WATCH))
    return reasons


def waiting_reasons(user, project, joined_at, now):
    if project is not None or joined_at is None:
        return []
    if now - joined_at >= timedelta(hours=WAITING_HOURS):
        return [reason('waiting', 'Ждёт плана больше суток', URGENT)]
    return []


def attention_for(coach, now=None):
    """[{user fields…, reasons: […]}] for the coach's clients that need a
    word, most urgent first."""

    from django.contrib.auth import get_user_model

    from coaching.access import coached_ids
    from coaching.models import CoachClient
    from training.models import Project

    users = get_user_model().objects
    now = now or timezone.now()
    today = timezone.localdate(now)
    ids = coached_ids(coach)
    projects = {p.user_id: p for p in Project.objects.filter(user_id__in=ids)}
    joined = dict(CoachClient.objects.filter(client_id__in=ids)
                  .values_list('client_id', 'joined_at'))
    rows = []
    for user in users.filter(pk__in=ids, is_active=True):
        project = projects.get(user.pk)
        reasons = (waiting_reasons(user, project, joined.get(user.pk), now)
                   + food_reasons(user, project, today)
                   + weight_reasons(user, project, today)
                   + checkin_reasons(user, today))
        if not reasons:
            continue
        reasons.sort(key=lambda r: -r['severity'])
        rows.append({
            'id': user.pk,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'gender': user.gender,
            'status': 'active' if project else 'waiting',
            'reasons': reasons,
            'score': sum(r['severity'] for r in reasons),
        })
    rows.sort(key=lambda r: (-r['score'], r['first_name']))
    return rows
