"""Which days of a program a client sees.

Calendar programs (one stream for everyone): day 1 is the program's
start date, day N falls on the N-th date from it, and a client sees the
days from the one they joined on. Personal programs: day 1 is the day the
client started. Either way a day opens on its date (in the client's time
zone); the first TRIAL_DAYS from joining are free, the rest need paid
access."""

from datetime import timedelta

TRIAL_DAYS = 7


def schedule_of(program):
    from programs.models import ProgramSchedule

    try:
        return program.schedule
    except ProgramSchedule.DoesNotExist:
        return None


def is_calendar(program):
    schedule = schedule_of(program)
    return bool(schedule and schedule.mode == schedule.Mode.CALENDAR
                and schedule.starts_on)


def origin(enrollment):
    """The date of day 1 for this client."""

    if is_calendar(enrollment.program):
        return enrollment.program.schedule.starts_on
    return enrollment.started_on


def day_date(enrollment, day):
    return origin(enrollment) + timedelta(days=day - 1)


def day_number(enrollment, date):
    return (date - origin(enrollment)).days + 1


def current_day(enrollment, today):
    return day_number(enrollment, today)


def trial_start(enrollment):
    """Joining before a calendar program starts: the free week begins with
    its first day."""

    return max(enrollment.started_on, origin(enrollment))


def trial_end(enrollment):
    return trial_start(enrollment) + timedelta(days=TRIAL_DAYS - 1)


def first_day(enrollment):
    """The earliest day the client sees (the one they joined on)."""

    return day_number(enrollment, trial_start(enrollment))


def trial_left(enrollment, today):
    if today > trial_end(enrollment):
        return 0
    return (trial_end(enrollment) - max(today, trial_start(enrollment))
            ).days + 1


def has_paid(enrollment, today):
    return bool(enrollment.paid_until and today <= enrollment.paid_until)


def day_state(day, enrollment, today):
    """'open', 'later' (its date hasn't come), 'before' (before the client
    joined) or 'paywall'."""

    if day > current_day(enrollment, today):
        return 'later'
    if day < first_day(enrollment):
        return 'before'
    if (day_date(enrollment, day) <= trial_end(enrollment)
            or has_paid(enrollment, today)):
        return 'open'
    return 'paywall'
