"""The admin's dashboard: a handful of numbers that show where clients are
lost and whether the tools work. Computed from the existing data on each
request (no tables of its own); fine for hundreds of clients."""

from datetime import timedelta
from statistics import median

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAdmin

User = get_user_model()

RETENTION_WINDOW = 7  # «still logging»: food or a check-in within a week


def share(part, whole):
    return round(part / whole * 100) if whole else None


def activity_days(user_ids, since, until):
    """{user_id: set(dates)} with food or a check-in in [since, until]."""

    from checkins.models import DailyCheckin
    from training.models import FoodDiary

    days = {}
    for uid, day in FoodDiary.objects.filter(
            user_id__in=user_ids, date__gte=since, date__lte=until,
            calories_actual__gt=0).values_list('user_id', 'date'):
        days.setdefault(uid, set()).add(day)
    for uid, day in DailyCheckin.objects.filter(
            user_id__in=user_ids, date__gte=since,
            date__lte=until).values_list('user_id', 'date'):
        days.setdefault(uid, set()).add(day)
    return days


def retention(clients, offset, today, period):
    """Of the clients who signed up in the period (and have been around
    `offset` + a week), the share active in the week starting `offset`
    days after sign-up."""

    cohort = [u for u in clients
              if timezone.localdate(u.date_joined) >= today - timedelta(
                  days=period + offset + RETENTION_WINDOW)
              and timezone.localdate(u.date_joined)
              <= today - timedelta(days=offset + RETENTION_WINDOW)]
    if not cohort:
        return {'percent': None, 'cohort': 0}
    earliest = min(timezone.localdate(u.date_joined) for u in cohort)
    days = activity_days([u.pk for u in cohort],
                         earliest + timedelta(days=offset), today)
    kept = 0
    for user in cohort:
        start = timezone.localdate(user.date_joined) + timedelta(days=offset)
        window = {start + timedelta(days=i)
                  for i in range(RETENTION_WINDOW)}
        if days.get(user.pk, set()) & window:
            kept += 1
    return {'percent': share(kept, len(cohort)), 'cohort': len(cohort)}


def clients_block(clients, with_plan, joined_ids, since):
    waiting = [u for u in clients
               if u.pk in joined_ids and u.pk not in with_plan]
    return {
        'total': len(clients),
        'active': len(with_plan),
        'waiting': len(waiting),
        'new': sum(1 for u in clients if u.date_joined >= since),
    }


def engagement_block(clients, with_plan, today, period):
    from training.models import FoodDiary

    planned = [u.pk for u in clients if u.pk in with_plan]
    week_ago = today - timedelta(days=6)
    food_days = {}
    for uid, day in FoodDiary.objects.filter(
            user_id__in=planned, date__gte=week_ago, date__lte=today,
            calories_actual__gt=0).values_list('user_id', 'date'):
        food_days.setdefault(uid, set()).add(day)
    logging = [len(food_days.get(uid, ())) for uid in planned]
    return {
        'food_days_per_week': (round(sum(logging) / len(logging), 1)
                               if logging else None),
        'active_week_percent': share(sum(1 for n in logging if n),
                                     len(planned)),
        'retention_7': retention(clients, 7, today, period),
        'retention_30': retention(clients, 30, today, period),
    }


def channels_block(clients):
    from tgbot.models import NotificationSettings, TelegramAccount

    ids = [u.pk for u in clients]
    telegram = set(TelegramAccount.objects.filter(
        user_id__in=ids, can_write=True).values_list('user_id', flat=True))
    reports = NotificationSettings.objects.filter(
        user_id__in=telegram, daily_report=True).count()
    fatsecret = sum(1 for u in clients
                    if u.fatsecret_token and u.fatsecret_secret)
    return {
        'fatsecret_percent': share(fatsecret, len(clients)),
        'telegram_percent': share(len(telegram), len(clients)),
        'reports_percent': share(reports, len(clients)),
    }


def course_block(clients, today):
    from course.models import Enrollment, Lesson, LessonRead

    total = Lesson.objects.filter(is_published=True).count()
    ids = [u.pk for u in clients]
    enrolled = list(Enrollment.objects.filter(user_id__in=ids)
                    .values_list('user_id', flat=True))
    reads = (LessonRead.objects
             .filter(user_id__in=enrolled, lesson__is_published=True)
             .values('user_id').annotate(n=Count('id')))
    read = {row['user_id']: row['n'] for row in reads}
    finished = {uid for uid in enrolled if total and read.get(uid, 0) >= total}
    by_id = {u.pk: u for u in clients}
    finished_users = [by_id[uid] for uid in finished]
    others = [u for u in clients if u.pk not in finished]
    return {
        'enrolled': len(enrolled),
        'finished': len(finished),
        'avg_read': (round(sum(read.get(uid, 0) for uid in enrolled)
                           / len(enrolled), 1) if enrolled else None),
        'total': total,
        # Does the onboarding work: kept on day 30, finished vs the rest.
        'retention_30_finished': retention(finished_users, 30, today, 365),
        'retention_30_others': retention(others, 30, today, 365),
    }


def coaches_block(today):
    from coaching.access import coached_ids
    from coaching.attention import attention_for
    from coaching.models import CoachClient, DayComment
    from training.models import Project

    rows = []
    week_ago = today - timedelta(days=6)
    for coach in User.objects.filter(role=User.Roles.COACH, is_active=True):
        ids = coached_ids(coach)
        planned = set(Project.objects.filter(user_id__in=ids)
                      .values_list('user_id', flat=True))
        waiting = CoachClient.objects.filter(
            client_id__in=ids).exclude(client_id__in=planned).count()
        rows.append({
            'username': coach.username,
            'name': (' '.join(p for p in (coach.first_name, coach.last_name)
                              if p) or coach.username),
            'clients': len(ids),
            'waiting': waiting,
            'attention': len(attention_for(coach)),
            'comments_week': DayComment.objects.filter(
                coach=coach, date__gte=week_ago).count(),
        })
    rows.sort(key=lambda r: -r['clients'])
    return rows


def applications_block(since):
    from questionnaire import flow
    from questionnaire.models import Questionnaire

    apps = list(Questionnaire.objects.filter(created_at__gte=since)
                .select_related('progress', 'user__project_user'))
    active = sum(1 for q in apps
                 if flow.stage_of(q) == flow.Stage.ACTIVE)
    hours = [(q.progress.first_response_at - q.created_at).total_seconds()
             / 3600 for q in apps
             if flow.getattr_progress(q) is not None
             and q.progress.first_response_at]
    return {
        'received': len(apps),
        'active': active,
        'active_percent': share(active, len(apps)),
        'median_response_hours': round(median(hours), 1) if hours else None,
    }


def analytics(period=30, now=None):
    from coaching.models import CoachClient
    from training.models import Project

    now = now or timezone.now()
    today = timezone.localdate(now)
    since = now - timedelta(days=period)
    clients = list(User.objects.filter(role=User.Roles.USER,
                                       is_active=True))
    ids = [u.pk for u in clients]
    with_plan = set(Project.objects.filter(user_id__in=ids)
                    .values_list('user_id', flat=True))
    joined = set(CoachClient.objects.filter(client_id__in=ids)
                 .values_list('client_id', flat=True))
    return {
        'period_days': period,
        'clients': clients_block(clients, with_plan, joined, since),
        'engagement': engagement_block(clients, with_plan, today, period),
        'channels': channels_block(clients),
        'course': course_block(clients, today),
        'coaches': coaches_block(today),
        'applications': applications_block(since),
        'payments': None,  # not in the app yet
    }


class AnalyticsView(APIView):
    """GET /api/admin/analytics/?days=7|30|90 — admin only."""

    permission_classes = (IsAuthenticated, IsAdmin)

    def get(self, request):
        try:
            days = int(request.query_params.get('days', 30))
        except ValueError:
            days = 30
        return Response(analytics(min(max(days, 1), 365)))
