"""Tell the admin about a client who signed up without a questionnaire and
without a coach — so a coach gets assigned to them too.

Not at sign-up itself: the account is inactive until the e-mail is
confirmed, and a questionnaire sent before sign-up is linked only after
the first login. Cron looks half an hour later, once per client."""

import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from coaching.models import CoachClient, NewClientNotice

logger = logging.getLogger(__name__)
User = get_user_model()

WAIT = timedelta(minutes=30)
# Older sign-ups aren't announced — they predate this notice.
LOOK_BACK = timedelta(days=7)


def clients_to_announce(now=None):
    from questionnaire.models import Questionnaire
    from training.models import Project

    now = now or timezone.now()
    candidates = User.objects.filter(
        role=User.Roles.USER,
        is_active=True,
        date_joined__lte=now - WAIT,
        date_joined__gte=now - LOOK_BACK,
        new_client_notice__isnull=True,
    )
    with_questionnaire = Questionnaire.objects.filter(
        user__in=candidates).values_list('user_id', flat=True)
    with_coach = CoachClient.objects.filter(
        client__in=candidates).values_list('client_id', flat=True)
    with_plan = Project.objects.filter(
        user__in=candidates).values_list('user_id', flat=True)
    return list(candidates.exclude(pk__in=with_questionnaire)
                .exclude(pk__in=with_coach).exclude(pk__in=with_plan)
                .order_by('date_joined'))


def message_for(users):
    base = settings.APP_BASE_URL.rstrip('/')
    lines = [f'Новый клиент без анкеты: {len(users)}'
             if len(users) > 1 else 'Новый клиент без анкеты']
    for user in users[:10]:
        name = ' '.join(p for p in (user.first_name, user.last_name) if p)
        lines.append(f'\n{name or user.username} (@{user.username})\n'
                     f'{user.email}\n'
                     f'Назначьте тренера: {base}/users/{user.username}')
    if len(users) > 10:
        lines.append(f'\n…и ещё {len(users) - 10}')
    return '\n'.join(lines)


def announce_new_clients(now=None):
    """Cron: one message to the admin chat; each client only once."""

    from tgbot.telegram_api import SENT, send_message

    users = clients_to_announce(now)
    chat_id = settings.TELEGRAM_NOTIFY_CHAT_ID
    if not users or not chat_id:
        return 0
    if send_message(chat_id, message_for(users)) != SENT:
        return 0
    NewClientNotice.objects.bulk_create(
        [NewClientNotice(client=user) for user in users],
        ignore_conflicts=True,
    )
    return len(users)
