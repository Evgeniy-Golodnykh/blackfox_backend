import hmac
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from tgbot.init_data import validate_init_data
from tgbot.link_codes import (
    LIFETIME_SECONDS, check_link_code, make_link_code, parse_link_code,
)
from tgbot import onboarding
from tgbot.models import NotificationSettings, TelegramAccount
from tgbot.scheduler import send_now
from tgbot.serializers import NotificationSettingsSerializer
from tgbot.telegram_api import SENT, send_message
from tgbot.services import TelegramTakenError, link_telegram
from users.serializers import CustomUserSerializer

User = get_user_model()

invalid_init_data_message = 'Не удалось проверить данные Telegram.'
not_linked_message = 'Этот Telegram не привязан к аккаунту.'
linked_elsewhere_message = 'Этот Telegram уже привязан к другому аккаунту.'


def link_state(user):
    """What a link code is bound to: the user's current Telegram ID."""

    account = TelegramAccount.objects.filter(user=user).first()
    return str(account.telegram_id) if account else ''


def init_data_from(request):
    value = request.data.get('init_data')
    return value if isinstance(value, str) and len(value) <= 4096 else ''


class TelegramLoginView(APIView):
    """POST /api/auth/telegram/ — sign in from inside the Mini App."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        tg_user = validate_init_data(init_data_from(request))
        if tg_user is None:
            return Response(
                {'detail': invalid_init_data_message},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        account = TelegramAccount.objects.select_related('user').filter(
            telegram_id=tg_user['id'],
        ).first()
        if account is None or not account.user.is_active:
            return Response(
                {'detail': not_linked_message},
                status=status.HTTP_404_NOT_FOUND,
            )
        refresh = RefreshToken.for_user(account.user)
        data = CustomUserSerializer(
            account.user, context={'request': request},
        ).data
        data.update({'access': str(refresh.access_token),
                     'refresh': str(refresh)})
        return Response(data)


class MyTelegramView(APIView):
    """GET/POST/DELETE /api/users/me/telegram/ — the signed-in user's link."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        account = TelegramAccount.objects.filter(user=request.user).first()
        return Response({
            'linked': account is not None,
            'username': account.username if account else '',
            'can_write': account.can_write if account else False,
        })

    def post(self, request):
        tg_user = validate_init_data(init_data_from(request))
        if tg_user is None:
            return Response(
                {'detail': invalid_init_data_message},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            _, first_time = link_telegram(request.user, tg_user['id'],
                                          tg_user.get('username', ''))
        except TelegramTakenError:
            return Response(
                {'detail': linked_elsewhere_message},
                status=status.HTTP_409_CONFLICT,
            )
        if first_time:
            onboarding.send_later(request.user, onboarding.linked)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def delete(self, request):
        TelegramAccount.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyNotificationsView(APIView):
    """GET/PATCH /api/users/me/notifications/ — what the bot sends."""

    permission_classes = (IsAuthenticated,)

    def get_object(self):
        settings_row, _ = NotificationSettings.objects.get_or_create(
            user=self.request.user,
        )
        return settings_row

    def get(self, request):
        return Response(NotificationSettingsSerializer(self.get_object()).data)

    def patch(self, request):
        serializer = NotificationSettingsSerializer(
            self.get_object(), data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


def set_all_notifications(telegram_id, enabled):
    """/start and /stop in the bot: every kind on or off at once."""

    account = TelegramAccount.objects.filter(telegram_id=telegram_id).first()
    if account is None:
        return False
    NotificationSettings.objects.update_or_create(
        user_id=account.user_id,
        defaults={flag: enabled for flag in NotificationSettings.FLAGS},
    )
    return True


class TelegramTestMessageView(APIView):
    """POST /api/users/me/telegram/test/ {"kind": …} — send yourself an
    example right now (daily_report, weekly_report or checkin)."""

    permission_classes = (IsAuthenticated,)
    throttle_scope = 'telegram_test'
    throttle_classes = (ScopedRateThrottle,)
    KINDS = ('daily_report', 'weekly_report', 'checkin')

    def post(self, request):
        kind = request.data.get('kind')
        if kind not in self.KINDS:
            return Response({'detail': 'Неизвестный вид сообщения.'},
                            status=status.HTTP_400_BAD_REQUEST)
        account = TelegramAccount.objects.filter(user=request.user).first()
        if account is None or not account.can_write:
            return Response({'detail': not_linked_message},
                            status=status.HTTP_409_CONFLICT)
        result = send_now(request.user, kind)
        if result is None:
            return Response(
                {'detail': 'Пока не из чего собрать отчёт — нет записей '
                           'в дневнике.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        if result != SENT:
            return Response({'detail': 'Telegram не принял сообщение.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response({'sent': True})


class TelegramLinkCodeView(APIView):
    """POST /api/users/me/telegram/link/ — a t.me link that links this
    account when opened in Telegram (for the browser and the apps)."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        code = make_link_code(request.user.pk, link_state(request.user))
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=LIFETIME_SECONDS,
        )
        return Response({
            'url': f'https://t.me/{settings.TELEGRAM_BOT_USERNAME}'
                   f'?start={code}',
            'expires_at': expires_at.isoformat(),
        })


def open_app_button(text, path='/stats'):
    url = f"{settings.APP_BASE_URL.rstrip('/')}{path}"
    return {'inline_keyboard': [[{'text': text, 'web_app': {'url': url}}]]}


def reply(chat_id, text, path='/stats', button='Открыть BFN', markup=None):
    """Answer within the webhook response — no extra call to Telegram."""

    return Response({
        'method': 'sendMessage',
        'chat_id': chat_id,
        'text': text,
        'reply_markup': markup or open_app_button(button, path),
    })


def reply_with(chat_id, message):
    text, markup = message
    return reply(chat_id, text, markup=markup)


class TelegramWebhookView(APIView):
    """POST /api/telegram/webhook/ — updates from the bot.

    Telegram proves it's Telegram with the secret set in setWebhook
    (X-Telegram-Bot-Api-Secret-Token). Always answers 200, so Telegram
    doesn't retry the same update forever.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request):
        secret = settings.TELEGRAM_WEBHOOK_SECRET
        received = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        if not secret or not hmac.compare_digest(received, secret):
            return Response(status=status.HTTP_404_NOT_FOUND)

        update = request.data if isinstance(request.data, dict) else {}
        if 'my_chat_member' in update:
            self.chat_member(update['my_chat_member'])
            return Response({})
        if isinstance(update.get('callback_query'), dict):
            return self.callback(update['callback_query'])
        message = update.get('message')
        if isinstance(message, dict):
            return self.message(message) or Response({})
        return Response({})

    def callback(self, query):
        """A tap on an inline button — only «Включить отчёты» for now."""

        sender = query.get('from') or {}
        answer = {'method': 'answerCallbackQuery',
                  'callback_query_id': str(query.get('id', ''))}
        account = TelegramAccount.objects.select_related('user').filter(
            telegram_id=sender.get('id'),
        ).first()
        if query.get('data') != onboarding.ENABLE_REPORTS or account is None:
            answer['text'] = not_linked_message if account is None else ''
            return Response(answer)
        onboarding.set_reports(account.user, True)
        text, markup = onboarding.reports_enabled()
        send_message(account.telegram_id, text, markup=markup)
        answer['text'] = 'Отчёты включены'
        return Response(answer)

    def chat_member(self, change):
        """Blocked the bot → stop writing; unblocked → may write again."""

        if not isinstance(change, dict):
            return
        chat = change.get('chat') or {}
        new_status = (change.get('new_chat_member') or {}).get('status')
        chat_id = chat.get('id')
        if chat.get('type') != 'private' or not isinstance(chat_id, int):
            return
        if new_status in ('kicked', 'member'):
            TelegramAccount.objects.filter(telegram_id=chat_id).update(
                can_write=new_status == 'member',
            )
        if new_status == 'kicked':
            # Blocked: switch everything off, so unblocking alone doesn't
            # bring the messages back — /start or the app does.
            set_all_notifications(chat_id, False)

    def message(self, message):
        chat = message.get('chat') or {}
        sender = message.get('from') or {}
        text = message.get('text')
        if chat.get('type') != 'private' or not isinstance(text, str):
            return None
        telegram_id = sender.get('id')
        if not isinstance(telegram_id, int):
            return None

        command, _, argument = text.strip().partition(' ')
        command = command.split('@')[0]
        account = TelegramAccount.objects.select_related('user').filter(
            telegram_id=telegram_id,
        ).first()

        if command == '/start' and argument.strip():
            return self.start_with(chat['id'], sender, account,
                                   argument.strip())
        if account is None:
            if command in ('/start', '/stop'):
                return reply_with(chat['id'], onboarding.welcome())
            return reply_with(chat['id'], onboarding.help_text())

        user = account.user
        if command == '/stop':
            set_all_notifications(telegram_id, False)
            return reply(
                chat['id'],
                'Готово, отчёты и напоминания выключены. Включить снова '
                '— /start или в настройках приложения.',
                path='/settings', button='Настройки',
            )
        if command == '/start':
            if not account.can_write:
                account.can_write = True
                account.save(update_fields=['can_write'])
            if onboarding.has_project(user):
                onboarding.set_reports(user, True)
                return reply_with(chat['id'], onboarding.reports_enabled())
            return reply_with(chat['id'], onboarding.linked(user))
        return reply_with(chat['id'], onboarding.help_text(user))

    def start_with(self, chat_id, sender, account, argument):
        """`/start <argument>`: a coach's join link or a link code."""

        if argument.startswith('join_'):
            return self.join_by_link(chat_id, account,
                                     argument[len('join_'):])
        return self.link_by_code(chat_id, sender.get('id'),
                                 sender.get('username', ''), argument)

    def join_by_link(self, chat_id, account, code):
        """A coach's link opened in the bot: join right away if this
        Telegram is linked to a client; otherwise open the join page."""

        from coaching.models import CoachInvite
        from coaching.services import (
            OtherCoachError, join_coach, notify_coach_of_new_client,
        )

        invite = CoachInvite.objects.select_related('coach').filter(
            code=code[:16], coach__is_active=True).first()
        if invite is None:
            return reply(chat_id, 'Ссылка тренера недействительна — '
                                  'попросите у тренера новую.')
        coach = invite.coach
        coach_name = ' '.join(
            part for part in (coach.first_name, coach.last_name) if part
        ) or coach.username
        if account is None or account.user.role != User.Roles.USER:
            return reply(
                chat_id,
                f'Вас приглашает тренер {coach_name}. Начните с анкеты — '
                '3 минуты, по ней тренер составит ваш план. После неё '
                'создадите аккаунт и будете у тренера.',
                path=f'/join/{invite.code}', button='Заполнить анкету',
            )
        try:
            new = join_coach(account.user, coach)
        except OtherCoachError:
            return reply(chat_id, 'Вы уже занимаетесь с другим тренером. '
                                  'Чтобы перейти, напишите администратору.')
        if new:
            notify_coach_of_new_client(coach, account.user)
        from questionnaire.models import Questionnaire
        if not Questionnaire.objects.filter(user=account.user).exists():
            return reply(
                chat_id,
                f'Готово: вы у тренера {coach_name}. Осталась анкета — '
                'без неё тренер не сможет составить план. Это 3 минуты.',
                path='/questionnaire', button='Заполнить анкету',
            )
        return reply(
            chat_id,
            f'Готово: вы у тренера {coach_name}. Он составит план — я '
            'напишу, когда он будет готов.',
        )

    def link_by_code(self, chat_id, telegram_id, username, code):
        parsed = parse_link_code(code)
        user = None
        if parsed:
            user = User.objects.filter(pk=parsed[0], is_active=True).first()
        if user is None or not check_link_code(parsed, link_state(user)):
            return reply(
                chat_id,
                'Ссылка устарела. Откройте настройки в приложении и нажмите '
                '«Подключить Telegram» ещё раз.',
                path='/settings', button='Открыть настройки',
            )
        try:
            link_telegram(user, telegram_id, username)
        except TelegramTakenError:
            return reply(chat_id, linked_elsewhere_message, path='/settings',
                         button='Открыть настройки')
        return reply_with(chat_id, onboarding.linked(user))
