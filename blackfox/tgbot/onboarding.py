"""What the bot says when someone arrives, links, asks for /help, and when
their coach creates the plan. Texts in one place, so they're easy to edit.

Reports start switched off for someone who links Telegram for the first
time: there's nothing to report until the coach has made a plan. Once
there is one, the bot offers a one-tap «Включить отчёты».
"""

import logging
import threading

from django.conf import settings

from tgbot.models import NotificationSettings, TelegramAccount

logger = logging.getLogger(__name__)

ENABLE_REPORTS = 'enable_reports'

WHAT_I_SEND = (
    'Что я присылаю:\n'
    '• 21:00 — отчёт за день картинкой: калории, БЖУ, серия\n'
    '• понедельник, 10:00 — итоги недели и вес\n'
    '• утром — напоминание о чек-ине\n'
    '• 20:00 — мягкое напоминание, если что-то забыто\n'
    'Время и что присылать — в настройках приложения. Выключить всё — /stop.'
)


def app_url(path):
    return f"{settings.APP_BASE_URL.rstrip('/')}{path}"


def web_app(text, path):
    return {'text': text, 'web_app': {'url': app_url(path)}}


def keyboard(*rows):
    return {'inline_keyboard': [list(row) for row in rows]}


def enable_button():
    return {'text': 'Включить отчёты', 'callback_data': ENABLE_REPORTS}


def has_project(user):
    from training.models import Project

    return Project.objects.filter(user=user).exists()


def has_fatsecret(user):
    return bool(user.fatsecret_token and user.fatsecret_secret)


def reports_on(user):
    prefs = NotificationSettings.objects.filter(user=user).first()
    return prefs is not None and any(
        getattr(prefs, flag) for flag in NotificationSettings.FLAGS
    )


def start_switched_off(user):
    """First link: reports off until there's a plan (kept if already set)."""

    NotificationSettings.objects.get_or_create(
        user=user,
        defaults={flag: False for flag in NotificationSettings.FLAGS},
    )


def set_reports(user, enabled):
    NotificationSettings.objects.update_or_create(
        user=user,
        defaults={flag: enabled for flag in NotificationSettings.FLAGS},
    )


# ----- messages: (text, reply_markup) ---------------------------------------

def welcome():
    """/start from someone whose Telegram isn't linked to an account."""

    return (
        'Привет! Я бот Black Fox Nutrition 🦊\n\n'
        'Помогаю держать питание в норме: каждый вечер присылаю отчёт за '
        'день, по понедельникам — итоги недели, и мягко напоминаю, если '
        'что-то забыто.\n\n'
        'Уже клиент — войдите в приложение, и Telegram подключится сам.\n'
        'Ещё нет — заполните короткую анкету, и мы подберём тренера.',
        keyboard([web_app('Войти', '/login')],
                 [web_app('Заполнить анкету', '/questionnaire')]),
    )


def linked(user):
    """Right after linking (from the bot or the app)."""

    name = (user.first_name or '').strip() or user.username
    lines = [f'Готово, {name}! Telegram подключён к BFN.', '', WHAT_I_SEND, '']
    rows = []
    if reports_on(user):
        lines.append('Отчёты включены.')
    elif has_project(user):
        lines.append('План от тренера уже есть — включить отчёты?')
        rows.append([enable_button()])
    else:
        lines.append('Пока отчёты выключены: они появятся, когда тренер '
                     'составит ваш план. Я напишу, когда он будет готов.')
    if not has_fatsecret(user):
        lines += ['', 'Для отчётов нужен дневник FatSecret — подключите его '
                      'в настройках приложения.']
        rows.append([web_app('Подключить FatSecret', '/settings')])
    rows.append([web_app('Открыть BFN', '/stats')])
    return '\n'.join(lines), keyboard(*rows)


def help_text(user=None):
    lines = [
        'Я бот Black Fox Nutrition.', '', WHAT_I_SEND, '',
        'Команды:',
        '/start — подключиться или снова включить отчёты',
        '/stop — выключить все отчёты и напоминания',
        '/help — это сообщение',
    ]
    if user is None:
        return '\n'.join(lines), keyboard([web_app('Войти', '/login')])
    return '\n'.join(lines), keyboard([web_app('Настройки', '/settings')])


def plan_ready(user):
    """The coach created the plan; reports are still off."""

    return (
        'Тренер составил ваш план 🎯\n\n'
        'Включить отчёты и напоминания в Telegram? Вечером пришлю, как '
        'прошёл день, по понедельникам — итоги недели.',
        keyboard([enable_button()], [web_app('Открыть план', '/stats')]),
    )


def reports_enabled():
    return (
        'Отчёты включены ✅ Первый придёт сегодня в 21:00, если в FatSecret '
        'будет еда за день. Время и что присылать — в настройках приложения.',
        keyboard([web_app('Настройки', '/settings')]),
    )


# ----- sending outside a webhook answer -----------------------------------

def send_later(user, build):
    """Send build(user) to the user's chat in the background, after the
    current transaction — never slows down or breaks the request."""

    from django.db import transaction

    from tgbot.telegram_api import send_message

    def send():
        account = TelegramAccount.objects.filter(user=user,
                                                 can_write=True).first()
        if account is None:
            return
        try:
            text, markup = build(user)
            send_message(account.telegram_id, text, markup=markup)
        except Exception as err:
            logger.warning('Bot message to %s failed: %s', user.pk,
                           type(err).__name__)

    transaction.on_commit(
        lambda: threading.Thread(target=send, daemon=True).start(),
    )
