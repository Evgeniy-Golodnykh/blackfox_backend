"""Codes for linking from outside Telegram: the app opens
t.me/<bot>?start=<code>, the person taps Start, the bot gets the code.

No table: the code is the user id, the time and an HMAC over both plus
the user's current link. Linking changes that link, so a code works once;
it also expires quickly. Telegram allows only A-Z a-z 0-9 _ - (64 chars).
"""

import base64
import hmac
import time

from django.utils.crypto import salted_hmac

LIFETIME_SECONDS = 15 * 60
SALT = 'tgbot.link_code'


def _signature(user_id, issued_at, link_state):
    value = f'{user_id}.{issued_at}.{link_state}'
    digest = salted_hmac(SALT, value).digest()
    return base64.urlsafe_b64encode(digest[:18]).decode()


def make_link_code(user_id, link_state, now=None):
    """link_state — the user's current Telegram ID, or '' if none."""

    issued_at = int(time.time() if now is None else now)
    signature = _signature(user_id, issued_at, link_state)
    return f'{user_id}_{issued_at:x}_{signature}'


def parse_link_code(code):
    """(user_id, issued_at, signature), or None if it isn't one."""

    if not isinstance(code, str) or len(code) > 64:
        return None
    parts = code.split('_', 2)
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1], 16), parts[2]
    except ValueError:
        return None


def check_link_code(parsed, link_state, now=None):
    """True if the parsed code is genuine, fresh and not used yet."""

    user_id, issued_at, signature = parsed
    expected = _signature(user_id, issued_at, link_state)
    if not hmac.compare_digest(signature, expected):
        return False
    now = time.time() if now is None else now
    return 0 <= now - issued_at <= LIFETIME_SECONDS
