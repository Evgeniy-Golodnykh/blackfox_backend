import json
import logging
import time

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SEND_URL = 'https://api.telegram.org/bot{token}/sendMessage'
PHOTO_URL = 'https://api.telegram.org/bot{token}/sendPhoto'

SENT = 'sent'
BLOCKED = 'blocked'  # the person blocked the bot / deleted the chat
FAILED = 'failed'    # anything else — worth trying again later


def web_app_button(text, path):
    url = f"{settings.APP_BASE_URL.rstrip('/')}{path}"
    return {'inline_keyboard': [[{'text': text, 'web_app': {'url': url}}]]}


def retry_after(response):
    try:
        return min(int(response.json()['parameters']['retry_after']), 30)
    except (ValueError, KeyError, TypeError):
        return 5


def post(token, payload, photo=None):
    """The response, or None if Telegram couldn't be reached."""

    try:
        if photo is None:
            return requests.post(SEND_URL.format(token=token), json=payload,
                                 timeout=10)
        return requests.post(
            PHOTO_URL.format(token=token), data=payload,
            files={'photo': ('report.jpg', photo, 'image/jpeg')},
            timeout=30,
        )
    except requests.RequestException as err:
        logger.warning('Telegram send to %s failed: %s',
                       payload['chat_id'], type(err).__name__)
        return None


def result_of(response, chat_id):
    if response is None:
        return FAILED
    if response.status_code == 200:
        return SENT
    if response.status_code == 403:
        return BLOCKED
    logger.warning('Telegram send to %s failed: HTTP %s', chat_id,
                   response.status_code)
    return FAILED


def send_with_retry(token, payload, photo=None):
    response = post(token, payload, photo)
    if response is not None and response.status_code == 429:
        time.sleep(retry_after(response))  # Telegram asked to slow down
        response = post(token, payload, photo)
    return result_of(response, payload['chat_id'])


def send_message(chat_id, text, button=None):
    """Send a plain-text message; button = (text, app path) or None.

    Never logs the text — it can contain health data."""

    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return FAILED
    payload = {'chat_id': chat_id, 'text': text,
               'disable_web_page_preview': True}
    if button:
        payload['reply_markup'] = web_app_button(*button)
    return send_with_retry(token, payload)


def send_photo(chat_id, jpeg, caption, button=None):
    """The picture report with a short caption (seen in the chat list)."""

    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return FAILED
    payload = {'chat_id': chat_id, 'caption': caption[:1024]}
    if button:
        payload['reply_markup'] = json.dumps(web_app_button(*button))
    return send_with_retry(token, payload, photo=jpeg)
