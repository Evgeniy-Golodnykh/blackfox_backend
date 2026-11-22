import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

API = 'https://api.telegram.org/bot{token}/{method}'


class Command(BaseCommand):
    help = 'Point the bot at /api/telegram/webhook/ (or --delete it).'

    def add_arguments(self, parser):
        parser.add_argument('--delete', action='store_true')

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError('TELEGRAM_BOT_TOKEN is not set')
        if options['delete']:
            method, payload = 'deleteWebhook', {}
        else:
            if not settings.TELEGRAM_WEBHOOK_SECRET:
                raise CommandError('TELEGRAM_WEBHOOK_SECRET is not set')
            method, payload = 'setWebhook', {
                'url': settings.TELEGRAM_WEBHOOK_URL,
                'secret_token': settings.TELEGRAM_WEBHOOK_SECRET,
                'allowed_updates': ['message', 'my_chat_member'],
            }
        try:
            response = requests.post(API.format(token=token, method=method),
                                     json=payload, timeout=10)
            result = response.json()
        except (requests.RequestException, ValueError) as err:
            # Not the error text: it can contain the URL with the token.
            raise CommandError(f'Telegram unreachable: {type(err).__name__}')
        if not result.get('ok'):
            raise CommandError(f"Telegram: {result.get('description')}")
        target = payload.get('url', 'deleted')
        self.stdout.write(self.style.SUCCESS(f'{method}: {target}'))
