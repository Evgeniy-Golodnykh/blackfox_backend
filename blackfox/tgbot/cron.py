import logging

from tgbot import scheduler

logger = logging.getLogger(__name__)


def send_due_notifications():
    """Cron, every 10 minutes: reports and reminders that are due."""

    results = scheduler.run()
    if results:
        counts = {}
        for _, _, result in results:
            counts[result] = counts.get(result, 0) + 1
        logger.info('Telegram notifications: %s', counts)
