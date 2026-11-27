"""Which days of a program a client sees: day N opens on the N-th
calendar day from the start (in the client's time zone); the first
TRIAL_DAYS are free, later days need paid access on the day they open."""

TRIAL_DAYS = 7


def current_day(enrollment, today):
    return (today - enrollment.started_on).days + 1


def has_paid(enrollment, today):
    return bool(enrollment.paid_until and today <= enrollment.paid_until)


def day_state(day, enrollment, today):
    """'open', 'later' (its day hasn't come) or 'paywall'."""

    if day > current_day(enrollment, today):
        return 'later'
    if day <= TRIAL_DAYS or has_paid(enrollment, today):
        return 'open'
    return 'paywall'
