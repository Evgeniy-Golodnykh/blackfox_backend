"""An application's way to a coach: stages, assigning, archive, reminders.

Health data in the answers is never logged or sent in notifications — only
the name, the contact and a link."""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from questionnaire.models import ApplicationProgress, Questionnaire

logger = logging.getLogger(__name__)

Stage = ApplicationProgress.Stage

ARCHIVE_AFTER = timedelta(days=30)
ANSWER_WITHIN = timedelta(hours=24)
# Older «Новые» aren't nagged about — they predate this reminder.
REMIND_ONLY_WITHIN = timedelta(days=14)
CLOSED = (Stage.DECLINED, Stage.NO_ANSWER)
# The old three-value status, kept in step for anything still reading it.
LEGACY_STATUS = {
    Stage.ACTIVE: Questionnaire.Status.ACCEPTED,
    Stage.DECLINED: Questionnaire.Status.DECLINED,
    Stage.NO_ANSWER: Questionnaire.Status.DECLINED,
}


def plan_of(questionnaire):
    """The linked client's project, if they have one (select_related
    'user__project_user' to avoid a query per application)."""

    from django.core.exceptions import ObjectDoesNotExist

    if questionnaire.user_id is None:
        return None
    try:
        return questionnaire.user.project_user
    except ObjectDoesNotExist:
        return None


def stage_of(questionnaire):
    progress = getattr_progress(questionnaire)
    if progress is not None:
        stage = progress.stage
    else:
        # Before this table: the old status is all there is.
        stage = {
            Questionnaire.Status.ACCEPTED: Stage.ACTIVE,
            Questionnaire.Status.DECLINED: Stage.DECLINED,
        }.get(questionnaire.status, Stage.NEW)
    # The client already has a plan (made before the stages, or while the
    # application sat elsewhere): they're being led — unless it was closed.
    if stage not in CLOSED and plan_of(questionnaire) is not None:
        return Stage.ACTIVE
    return stage


def getattr_progress(questionnaire):
    try:
        return questionnaire.progress
    except ApplicationProgress.DoesNotExist:
        return None


def is_archived(questionnaire, now=None):
    progress = getattr_progress(questionnaire)
    if progress is None or progress.stage not in CLOSED:
        return False
    changed = progress.stage_changed_at or questionnaire.created_at
    return changed < (now or timezone.now()) - ARCHIVE_AFTER


def archived_filter(now=None):
    """Kwargs selecting archived applications (for .filter / .exclude)."""

    return {
        'progress__stage__in': CLOSED,
        'progress__stage_changed_at__lt': (now or timezone.now())
        - ARCHIVE_AFTER,
    }


def progress_for(questionnaire):
    progress, _ = ApplicationProgress.objects.get_or_create(
        questionnaire=questionnaire,
        defaults={'stage': stage_of(questionnaire)},
    )
    questionnaire.progress = progress
    return progress


def set_stage(questionnaire, stage, reason='', coach=None, now=None):
    """Move the application to `stage`, stamping the funnel's times."""

    now = now or timezone.now()
    progress = progress_for(questionnaire)
    if progress.stage == Stage.NEW and stage != Stage.NEW:
        progress.first_response_at = progress.first_response_at or now
    if stage == Stage.ASSIGNED:
        progress.assigned_at = progress.assigned_at or now
        progress.coach = coach
    if stage == Stage.ACTIVE:
        progress.active_at = progress.active_at or now
    progress.reason = reason if stage in CLOSED else ''
    if progress.stage != stage:
        progress.stage_changed_at = now
    progress.stage = stage
    progress.save()
    status = LEGACY_STATUS.get(stage, Questionnaire.Status.NEW)
    if questionnaire.status != status:
        questionnaire.status = status
        questionnaire.save(update_fields=['status'])
    return progress


class AssignError(Exception):
    """The linked client already works with another coach."""


def assign_coach(questionnaire, coach):
    """Admin: give the application to a coach. A linked account goes to
    the coach's clients right away (as «Ждёт плана»); otherwise it waits
    in the coach's «Заявки» until the person signs up."""

    from coaching.models import CoachClient
    from training.models import Project

    user = questionnaire.user
    with transaction.atomic():
        project = (Project.objects.filter(user=user).first()
                   if user is not None else None)
        if project is not None and project.coach_id != coach.pk:
            raise AssignError
        if user is not None:
            CoachClient.objects.update_or_create(
                client=user,
                defaults={'coach': coach,
                          'source': CoachClient.Source.ADMIN},
            )
        set_stage(questionnaire, Stage.ASSIGNED, coach=coach)
        if project is not None:  # the plan is already there
            set_stage(questionnaire, Stage.ACTIVE)
    notify_coach_of_application(coach, questionnaire)
    return questionnaire.progress


def follow_assigned_coach(questionnaire):
    """The application was just linked to an account: if a coach is
    assigned, the client goes to them."""

    from coaching.models import CoachClient
    from coaching.services import OtherCoachError, join_coach

    progress = getattr_progress(questionnaire)
    if (progress is None or progress.coach is None
            or questionnaire.user is None):
        return
    try:
        join_coach(questionnaire.user, progress.coach,
                   source=CoachClient.Source.ADMIN)
    except OtherCoachError:
        logger.info('Application %s: client already has another coach',
                    questionnaire.pk)


def mark_active_for(user):
    """The client got a plan: their applications are «На ведении»."""

    for questionnaire in Questionnaire.objects.filter(user=user).exclude(
            progress__stage=Stage.ACTIVE).select_related('progress'):
        if stage_of(questionnaire) in CLOSED:
            continue
        set_stage(questionnaire, Stage.ACTIVE)


def applicant(questionnaire):
    answers = questionnaire.answers or {}
    name = str(answers.get('full_name') or 'без имени')[:100]
    contact = str(answers.get('contact') or '—')[:100]
    return name, contact


def notify_coach_of_application(coach, questionnaire):
    from tgbot import onboarding

    name, contact = applicant(questionnaire)
    linked = questionnaire.user is not None
    path = ('/clients' if linked
            else f'/clients/applications/{questionnaire.pk}')

    def build(_coach):
        return (
            f'Вам назначена анкета: {name}\n{contact}\n\n'
            + ('Клиент уже в приложении — он в «Моих клиентах» со статусом '
               '«Ждёт плана».' if linked else
               'Человек ещё не зарегистрирован. Напишите ему и отправьте '
               'приглашение — ссылка в анкете.'),
            onboarding.keyboard([onboarding.web_app('Открыть анкету', path)]),
        )

    onboarding.send_later(coach, build)


# ----- admin reminder -------------------------------------------------------

def stale_new(now=None):
    """«Новые» waiting over 24 hours that nobody was reminded about."""

    now = now or timezone.now()
    candidates = Questionnaire.objects.filter(
        created_at__lt=now - ANSWER_WITHIN,
        created_at__gte=now - REMIND_ONLY_WITHIN,
    ).select_related('progress', 'user__project_user')
    return [q for q in candidates
            if stage_of(q) == Stage.NEW
            and (getattr_progress(q) is None
                 or getattr_progress(q).reminded_at is None)]


def remind_admin(now=None):
    """Cron: one message listing applications left «Новыми» for a day."""

    from tgbot.telegram_api import SENT, send_message

    now = now or timezone.now()
    stale = stale_new(now)
    chat_id = settings.TELEGRAM_NOTIFY_CHAT_ID
    if not stale or not chat_id:
        return 0
    base = settings.APP_BASE_URL.rstrip('/')
    lines = [f'⏰ Анкеты без ответа больше суток: {len(stale)}']
    for q in stale[:10]:
        name, contact = applicant(q)
        lines.append(f'\n№{q.pk} · {name} · {contact}\n'
                     f'{base}/applications/{q.pk}')
    if len(stale) > 10:
        lines.append(f'\n…и ещё {len(stale) - 10}')
    if send_message(chat_id, '\n'.join(lines)) != SENT:
        return 0
    for q in stale:
        progress = progress_for(q)
        progress.reminded_at = now
        progress.save(update_fields=['reminded_at'])
    return len(stale)


# ----- funnel ---------------------------------------------------------------

def funnel(weeks=8, now=None):
    """Per week of arrival: received → contacted → coach → active, and the
    median hours to the first response. Payments aren't in the app yet."""

    now = now or timezone.now()
    today = timezone.localdate(now)
    monday = today - timedelta(days=today.weekday())
    start = monday - timedelta(weeks=weeks - 1)
    rows = {}
    for i in range(weeks):
        week = start + timedelta(weeks=i)
        rows[week] = {'week': week.isoformat(), 'received': 0,
                      'contacted': 0, 'assigned': 0, 'active': 0,
                      'paid': None, 'response_hours': []}
    applications = Questionnaire.objects.filter(
        created_at__date__gte=start).select_related('progress',
                                                    'user__project_user')
    for q in applications:
        created = timezone.localdate(q.created_at)
        row = rows.get(created - timedelta(days=created.weekday()))
        if row is None:
            continue
        progress = getattr_progress(q)
        stage = stage_of(q)
        row['received'] += 1
        responded = (progress.first_response_at if progress else None)
        if responded or stage != Stage.NEW:
            row['contacted'] += 1
        if (progress and progress.assigned_at) or stage == Stage.ACTIVE:
            row['assigned'] += 1
        if (progress and progress.active_at) or stage == Stage.ACTIVE:
            row['active'] += 1
        if responded:
            row['response_hours'].append(
                (responded - q.created_at).total_seconds() / 3600)
    result = []
    for row in rows.values():
        hours = sorted(row.pop('response_hours'))
        row['median_response_hours'] = (
            round(hours[len(hours) // 2], 1) if hours else None)
        result.append(row)
    return result
