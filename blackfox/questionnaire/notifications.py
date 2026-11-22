import logging
import threading

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_SEND_URL = 'https://api.telegram.org/bot{token}/sendMessage'


def build_message(questionnaire):
    """Only a pointer: name, contact and a link — never the answers.

    Plain text (no parse_mode): name and contact come from an anonymous
    caller, so nothing in them may be read as markup.
    """

    answers = questionnaire.answers or {}
    name = str(answers.get('full_name') or 'без имени')[:100]
    contact = str(answers.get('contact') or '—')[:100]
    base_url = settings.APP_BASE_URL.rstrip('/')
    return (
        f'Новая анкета №{questionnaire.pk}\n'
        f'{name}\n'
        f'{contact}\n'
        f'{base_url}/more/applications/{questionnaire.pk}'
    )


def notify_new_questionnaire(questionnaire):
    """Tell the owner in Telegram, in the background.

    Skipped when not configured; a failure only goes to the log and never
    breaks the submit.
    """

    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_NOTIFY_CHAT_ID
    if not token or not chat_id:
        return
    text = build_message(questionnaire)
    pk = questionnaire.pk

    def send():
        try:
            response = requests.post(
                TELEGRAM_SEND_URL.format(token=token),
                json={
                    'chat_id': chat_id,
                    'text': text,
                    'disable_web_page_preview': True,
                },
                timeout=5,
            )
            response.raise_for_status()
        except Exception as err:
            # The error's text can contain the URL, and so the bot token.
            logger.warning(
                'Telegram notification for questionnaire %s failed: %s',
                pk, type(err).__name__,
            )

    threading.Thread(target=send, daemon=True).start()
