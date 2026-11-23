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
        f'{base_url}/applications/{questionnaire.pk}'
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


MONTHS = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля',
          'августа', 'сентября', 'октября', 'ноября', 'декабря')


def answer_by(questionnaire):
    """«25 ноября, 14:30» — a day after the submit, Moscow time."""

    from datetime import timedelta
    from zoneinfo import ZoneInfo

    due = (questionnaire.created_at + timedelta(hours=24)).astimezone(
        ZoneInfo('Europe/Moscow'))
    return f'{due.day} {MONTHS[due.month - 1]}, {due:%H:%M}'


def applicant_reply(questionnaire, plan):
    lines = [
        'Анкета получена ✅',
        f'Тренер напишет вам до {answer_by(questionnaire)} (МСК).',
    ]
    if plan:
        lines += [
            '',
            'Ваш стартовый план на каждый день:',
            f'• {plan["calories"]} ккал',
            f'• белки {plan["protein"]} г · жиры {plan["fat"]} г · '
            f'углеводы {plan["carbs"]} г',
            '',
            'Это ориентир по формуле — тренер уточнит его после разбора '
            'анкеты.',
        ]
    lines += ['', 'Создайте аккаунт в приложении — там дневник и связь с '
                  'тренером.']
    return '\n'.join(lines)


def reply_to_applicant(questionnaire, telegram_id, plan):
    """Answer the sender in the bot (sent from the Mini App), in the
    background. Fails quietly if they never started the bot."""

    from tgbot.telegram_api import send_message

    text = applicant_reply(questionnaire, plan)
    pk = questionnaire.pk

    def send():
        try:
            send_message(telegram_id, text, button=(
                'Открыть приложение', '/signup?from=questionnaire'))
        except Exception as err:
            logger.warning('Applicant reply for questionnaire %s failed: %s',
                           pk, type(err).__name__)

    threading.Thread(target=send, daemon=True).start()
