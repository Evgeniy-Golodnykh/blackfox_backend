from django.db import transaction

from coaching.models import CoachClient


class OtherCoachError(Exception):
    """The client already works with a different coach."""


def join_coach(client, coach, source=CoachClient.Source.INVITE):
    """Put the client with this coach. Returns True if they're new to the
    coach, False if they were already there. A client with another coach —
    by project or by link — is refused: only an admin moves clients."""

    from training.models import Project

    with transaction.atomic():
        project = Project.objects.filter(user=client).first()
        if project is not None and project.coach_id != coach.pk:
            raise OtherCoachError
        link = CoachClient.objects.select_for_update().filter(
            client=client).first()
        if link is not None:
            if link.coach_id != coach.pk:
                raise OtherCoachError
            return False
        CoachClient.objects.create(client=client, coach=coach, source=source)
    return True


def notify_coach_of_new_client(coach, client):
    """Tell the coach in Telegram, after the commit, in the background."""

    from tgbot import onboarding

    parts = [client.first_name, client.last_name]
    full_name = ' '.join(part for part in parts if part)
    name = full_name or client.username

    def build(_coach):
        return (
            f'Новый клиент по вашей ссылке: {name} 🎉\n\n'
            'Он в «Моих клиентах» со статусом «Ждёт плана» — откройте '
            'анкету и составьте план.',
            onboarding.keyboard([onboarding.web_app('Мои клиенты',
                                                    '/clients')]),
        )

    onboarding.send_later(coach, build)
