from django.db import IntegrityError, transaction

from tgbot.models import TelegramAccount
from tgbot.onboarding import start_switched_off


class TelegramTakenError(Exception):
    """This Telegram account belongs to another user."""


def link_telegram(user, telegram_id, username=''):
    """Link (or re-link) the user's Telegram account. Returns (account,
    first_time) — first_time when this user had no Telegram linked before.

    One Telegram account per user and one user per Telegram account: a
    user who links a new one replaces the old link; a Telegram account
    already linked to someone else is refused, never moved.
    """

    username = (username or '')[:64]
    with transaction.atomic():
        taken = TelegramAccount.objects.filter(
            telegram_id=telegram_id,
        ).exclude(user=user).exists()
        if taken:
            raise TelegramTakenError
        first_time = not TelegramAccount.objects.filter(user=user).exists()
        try:
            account, _ = TelegramAccount.objects.update_or_create(
                user=user,
                defaults={
                    'telegram_id': telegram_id,
                    'username': username,
                    'can_write': True,
                },
            )
        except IntegrityError:  # linked elsewhere at the same moment
            raise TelegramTakenError
        if first_time:
            start_switched_off(user)
    return account, first_time
