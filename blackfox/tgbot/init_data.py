"""Checking Telegram Mini App launch data (Telegram.WebApp.initData).

Only data whose signature checks out on the server can be trusted; the
unsigned copy on the client can be faked.
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from django.conf import settings

MAX_AGE_SECONDS = 24 * 60 * 60


def validate_init_data(init_data, max_age=MAX_AGE_SECONDS, now=None):
    """The Telegram user dict if init_data is genuine and fresh, else None."""

    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not isinstance(init_data, str) or not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True,
                               strict_parsing=True))
    except ValueError:
        return None
    received_hash = pairs.pop('hash', '')
    if not received_hash:
        return None

    check_string = '\n'.join(f'{k}={v}' for k, v in sorted(pairs.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    expected = hmac.new(
        secret, check_string.encode(), hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        return None

    try:
        auth_date = int(pairs.get('auth_date', '0'))
        user = json.loads(pairs.get('user', 'null'))
    except ValueError:
        return None
    now = time.time() if now is None else now
    if now - auth_date > max_age:
        return None
    if not isinstance(user, dict) or not isinstance(user.get('id'), int):
        return None
    return user
