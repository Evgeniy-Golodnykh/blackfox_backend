import logging

from tgbot import scheduler

logger = logging.getLogger(__name__)


def send_due_notifications():
    """Cron, every 10 minutes: reports and reminders that are due, and the
    admin's nudge about applications left «Новыми» for a day."""

    from questionnaire.flow import remind_admin

    try:
        reminded = remind_admin()
        if reminded:
            logger.info('Admin reminded about %s applications', reminded)
    except Exception as err:
        logger.warning('Application reminder failed: %s', type(err).__name__)

    results = scheduler.run()
    if results:
        counts = {}
        for _, _, result in results:
            counts[result] = counts.get(result, 0) + 1
        logger.info('Telegram notifications: %s', counts)
