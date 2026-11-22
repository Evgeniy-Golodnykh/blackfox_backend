from django.core.management.base import BaseCommand

from tgbot import scheduler


class Command(BaseCommand):
    help = ('Send the Telegram reports and reminders that are due now. '
            '--dry-run prints them instead.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--user', action='append', dest='users',
                            help='only these usernames (repeatable)')
        parser.add_argument('--at', help='pretend it is this Moscow time, '
                                         '"YYYY-MM-DD HH:MM" (dry-run only)')
        parser.add_argument('--no-refresh', action='store_true',
                            help="don't pull fresh food from FatSecret")

    def handle(self, *args, **options):
        now = scheduler.as_local(options['at']) if options['at'] else None
        dry_run = options['dry_run'] or now is not None
        results = scheduler.run(now=now, dry_run=dry_run,
                                usernames=options['users'],
                                refresh=not options['no_refresh'])
        for username, message, result in results:
            self.stdout.write(f'--- {username} · {message.kind} · {result}')
            if dry_run:
                self.stdout.write(message.text)
        self.stdout.write(self.style.SUCCESS(f'{len(results)} message(s)'))
