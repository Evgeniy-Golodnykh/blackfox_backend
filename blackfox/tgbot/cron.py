import logging

from tgbot import scheduler

logger = logging.getLogger(__name__)


def housekeeping_jobs():
    """(name, job) pairs run before the messages; each returns a count."""

    from coaching.comments import purge_old
    from coaching.notices import announce_new_clients
    from programs.alerts import alert_schedule_gaps
    from questionnaire.flow import remind_admin

    return (
        # The admin's nudge about applications left «Новыми» for a day.
        ('applications reminded', remind_admin),
        # Coaches' day comments live two weeks.
        ('old day comments deleted', purge_old),
        # Clients who signed up without a questionnaire or a coach.
        ('new clients announced', announce_new_clients),
        # Calendar programs about to run out of written workouts.
        ('program gaps alerted', alert_schedule_gaps),
    )


def send_due_notifications():
    """Cron, every 10 minutes: the housekeeping above, then the reports
    and reminders that are due. One failing job doesn't stop the rest."""

    for name, job in housekeeping_jobs():
        try:
            count = job()
            if count:
                logger.info('%s: %s', name, count)
        except Exception as err:
            logger.warning('%s failed: %s', name, type(err).__name__)

    results = scheduler.run()
    if results:
        counts = {}
        for _, _, result in results:
            counts[result] = counts.get(result, 0) + 1
        logger.info('Telegram notifications: %s', counts)
