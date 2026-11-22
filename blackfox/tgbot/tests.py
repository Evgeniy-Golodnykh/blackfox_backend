import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, urlencode, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from tgbot.init_data import validate_init_data
from tgbot.link_codes import check_link_code, make_link_code, parse_link_code
from tgbot.models import NotificationSettings, TelegramAccount

User = get_user_model()

BOT_TOKEN = '123456:test-token'
SECRET = 'webhook-secret'
TG_ID = 777000111

LOGIN_URL = '/api/auth/telegram/'
ME_URL = '/api/users/me/telegram/'
LINK_URL = '/api/users/me/telegram/link/'
WEBHOOK_URL = '/api/telegram/webhook/'


def make_init_data(tg_id=TG_ID, username='anna_tg', auth_date=None,
                   token=BOT_TOKEN):
    """What Telegram puts in WebApp.initData, signed with the bot token."""

    fields = {
        'auth_date': str(int(time.time()) if auth_date is None
                         else auth_date),
        'query_id': 'AAE',
        'user': json.dumps({'id': tg_id, 'first_name': 'Анна',
                            'username': username}),
    }
    check_string = '\n'.join(f'{k}={v}' for k, v in sorted(fields.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    fields['hash'] = hmac.new(
        secret, check_string.encode(), hashlib.sha256,
    ).hexdigest()
    return urlencode(fields)


def make_user(name, **extra):
    return User.objects.create_user(
        username=name, email=f'{name}@example.com',
        password='Str0ng-pass-123', gender=User.Gender.FEMALE, **extra,
    )


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
class InitDataTests(TestCase):

    def test_genuine_data_gives_the_user(self):
        user = validate_init_data(make_init_data())
        self.assertEqual(user['id'], TG_ID)
        self.assertEqual(user['username'], 'anna_tg')

    def test_tampered_data_is_rejected(self):
        data = make_init_data().replace('anna_tg', 'someone')
        self.assertIsNone(validate_init_data(data))

    def test_other_bots_signature_is_rejected(self):
        self.assertIsNone(
            validate_init_data(make_init_data(token='999:other')),
        )

    def test_old_data_is_rejected(self):
        old = int(time.time()) - 25 * 60 * 60
        self.assertIsNone(validate_init_data(make_init_data(auth_date=old)))

    def test_garbage_is_rejected(self):
        for value in ('', 'hash=abc', 'not a query', None, 42):
            self.assertIsNone(validate_init_data(value))

    @override_settings(TELEGRAM_BOT_TOKEN='')
    def test_nothing_is_valid_without_a_token(self):
        self.assertIsNone(validate_init_data(make_init_data()))


class LinkCodeTests(TestCase):

    def test_code_fits_telegram_start_parameter(self):
        code = make_link_code(123456, '')
        self.assertLessEqual(len(code), 64)
        self.assertRegex(code, r'^[A-Za-z0-9_-]+$')

    def test_code_checks_out_once_and_expires(self):
        now = time.time()
        parsed = parse_link_code(make_link_code(5, '', now=now))
        self.assertTrue(check_link_code(parsed, '', now=now + 60))
        # After linking, the user's link state changes — the code is spent.
        self.assertFalse(check_link_code(parsed, str(TG_ID), now=now + 60))
        self.assertFalse(check_link_code(parsed, '', now=now + 16 * 60))

    def test_forged_code_is_rejected(self):
        code = make_link_code(5, '')
        user_id, issued_at, signature = parse_link_code(code)
        self.assertFalse(
            check_link_code((6, issued_at, signature), ''),
        )
        self.assertIsNone(parse_link_code('nonsense'))


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
class LoginAndLinkTests(APITestCase):

    def setUp(self):
        self.user = make_user('anna')
        self.other = make_user('olga')

    def test_login_with_linked_telegram_gives_tokens(self):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        response = self.client.post(
            LOGIN_URL, {'init_data': make_init_data()}, format='json',
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('access', data)
        self.assertIn('refresh', data)
        self.assertEqual(data['username'], 'anna')
        me = self.client.get(
            '/api/users/me/', HTTP_AUTHORIZATION=f"Bearer {data['access']}",
        )
        self.assertEqual(me.json()['username'], 'anna')

    def test_login_unlinked_is_404_and_bad_data_401(self):
        response = self.client.post(
            LOGIN_URL, {'init_data': make_init_data()}, format='json',
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            LOGIN_URL, {'init_data': 'hash=forged'}, format='json',
        )
        self.assertEqual(response.status_code, 401)

    def test_inactive_user_cannot_log_in(self):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        response = self.client.post(
            LOGIN_URL, {'init_data': make_init_data()}, format='json',
        )
        self.assertEqual(response.status_code, 404)

    def test_link_from_mini_app(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(ME_URL).json()['linked'], False)

        response = self.client.post(
            ME_URL, {'init_data': make_init_data()}, format='json',
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            self.client.get(ME_URL).json(),
            {'linked': True, 'username': 'anna_tg', 'can_write': True},
        )

    def test_relinking_replaces_the_old_telegram(self):
        TelegramAccount.objects.create(user=self.user, telegram_id=1)
        self.client.force_authenticate(self.user)
        self.client.post(ME_URL, {'init_data': make_init_data()},
                         format='json')
        self.assertEqual(
            TelegramAccount.objects.get(user=self.user).telegram_id, TG_ID,
        )

    def test_telegram_of_another_user_is_409(self):
        TelegramAccount.objects.create(user=self.other, telegram_id=TG_ID)
        self.client.force_authenticate(self.user)
        response = self.client.post(
            ME_URL, {'init_data': make_init_data()}, format='json',
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            TelegramAccount.objects.get(telegram_id=TG_ID).user, self.other,
        )

    def test_link_with_bad_data_is_400(self):
        self.client.force_authenticate(self.user)
        response = self.client.post(
            ME_URL, {'init_data': 'hash=x'}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_unlink(self):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.delete(ME_URL).status_code, 204)
        self.assertFalse(TelegramAccount.objects.exists())

    def test_endpoints_need_a_login(self):
        self.assertEqual(self.client.get(ME_URL).status_code, 401)
        self.assertEqual(self.client.post(LINK_URL).status_code, 401)


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN,
                   TELEGRAM_WEBHOOK_SECRET=SECRET,
                   TELEGRAM_BOT_USERNAME='bfn_test_bot',
                   APP_BASE_URL='https://app.example.test')
class WebhookTests(APITestCase):

    def setUp(self):
        self.user = make_user('anna', first_name='Анна')

    def post_update(self, update, secret=SECRET):
        return self.client.post(
            WEBHOOK_URL, update, format='json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret,
        )

    def start(self, argument='', tg_id=TG_ID):
        text = f'/start {argument}'.strip()
        return self.post_update({'update_id': 1, 'message': {
            'message_id': 1, 'text': text,
            'chat': {'id': tg_id, 'type': 'private'},
            'from': {'id': tg_id, 'username': 'anna_tg'},
        }})

    def link_code(self):
        self.client.force_authenticate(self.user)
        url = self.client.post(LINK_URL).json()['url']
        self.client.force_authenticate(None)
        self.assertTrue(url.startswith('https://t.me/bfn_test_bot?start='))
        return parse_qs(urlparse(url).query)['start'][0]

    def test_wrong_or_missing_secret_is_404(self):
        self.assertEqual(self.start().status_code, 200)
        self.assertEqual(
            self.post_update({'update_id': 1}, secret='nope').status_code,
            404,
        )

    @override_settings(TELEGRAM_WEBHOOK_SECRET='')
    def test_webhook_is_off_without_a_secret(self):
        self.assertEqual(self.post_update({}, secret='').status_code, 404)

    def test_start_with_code_links_and_replies(self):
        response = self.start(self.link_code())

        account = TelegramAccount.objects.get(user=self.user)
        self.assertEqual(account.telegram_id, TG_ID)
        self.assertEqual(account.username, 'anna_tg')
        body = response.json()
        self.assertEqual(body['method'], 'sendMessage')
        self.assertEqual(body['chat_id'], TG_ID)
        self.assertIn('Анна', body['text'])
        urls = [b['web_app']['url']
                for row in body['reply_markup']['inline_keyboard']
                for b in row if 'web_app' in b]
        self.assertIn('https://app.example.test/stats', urls)

    def test_code_works_once(self):
        code = self.link_code()
        self.start(code)
        response = self.start(code, tg_id=TG_ID + 1)

        self.assertIn('устарела', response.json()['text'])
        self.assertEqual(
            TelegramAccount.objects.get(user=self.user).telegram_id, TG_ID,
        )

    def test_bad_code_links_nothing(self):
        response = self.start('1_abc_forged')
        self.assertIn('устарела', response.json()['text'])
        self.assertFalse(TelegramAccount.objects.exists())

    def test_plain_start_when_not_linked_points_to_login(self):
        body = self.start().json()
        self.assertIn('войдите', body['text'])
        button = body['reply_markup']['inline_keyboard'][0][0]
        self.assertTrue(button['web_app']['url'].endswith('/login'))

    def test_block_and_unblock(self):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)

        def member(status):
            return self.post_update({'update_id': 2, 'my_chat_member': {
                'chat': {'id': TG_ID, 'type': 'private'},
                'new_chat_member': {'status': status},
            }})

        member('kicked')
        self.assertFalse(TelegramAccount.objects.get().can_write)
        member('member')
        self.assertTrue(TelegramAccount.objects.get().can_write)

        TelegramAccount.objects.update(can_write=False)
        self.start()
        self.assertTrue(TelegramAccount.objects.get().can_write)

    def test_group_messages_and_junk_are_ignored(self):
        response = self.post_update({'update_id': 3, 'message': {
            'text': '/start', 'chat': {'id': -5, 'type': 'group'},
            'from': {'id': TG_ID},
        }})
        self.assertEqual(response.json(), {})
        self.assertEqual(self.post_update({'junk': True}).json(), {})


NOTIFY_URL = '/api/users/me/notifications/'


class NotificationSettingsTests(APITestCase):

    def setUp(self):
        self.user = make_user('anna')
        self.client.force_authenticate(self.user)

    def test_defaults_on_first_read(self):
        self.assertEqual(self.client.get(NOTIFY_URL).json(), {
            'telegram_linked': False,
            'daily_report': True, 'weekly_report': True,
            'checkin_reminder': True, 'reminders': True,
            'checkin_time': '08:00', 'report_time': '21:00',
            'timezone': 'Europe/Moscow',
        })

    def test_linked_means_linked_and_not_blocked(self):
        account = TelegramAccount.objects.create(user=self.user,
                                                 telegram_id=TG_ID)
        self.assertTrue(self.client.get(NOTIFY_URL).json()['telegram_linked'])
        account.can_write = False
        account.save()
        self.assertFalse(self.client.get(NOTIFY_URL).json()['telegram_linked'])

    def test_patch_one_field(self):
        response = self.client.patch(NOTIFY_URL, {'report_time': '22:00'},
                                     format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['report_time'], '22:00')
        self.assertEqual(response.json()['checkin_time'], '08:00')

    def test_patch_rejects_bad_values_and_ignores_linked(self):
        for patch in ({'report_time': '19:00'}, {'checkin_time': '8:00'},
                      {'timezone': 'Mars/Olympus'}):
            with self.subTest(patch=patch):
                response = self.client.patch(NOTIFY_URL, patch, format='json')
                self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            NOTIFY_URL, {'telegram_linked': True, 'timezone': 'Asia/Omsk'},
            format='json',
        )
        self.assertEqual(response.json()['timezone'], 'Asia/Omsk')
        self.assertFalse(response.json()['telegram_linked'])

    def test_needs_a_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(NOTIFY_URL).status_code, 401)


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN,
                   TELEGRAM_WEBHOOK_SECRET=SECRET)
class BotCommandTests(APITestCase):

    def setUp(self):
        self.user = make_user('anna')
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)

    def command(self, text):
        return self.client.post(WEBHOOK_URL, {'update_id': 1, 'message': {
            'text': text, 'chat': {'id': TG_ID, 'type': 'private'},
            'from': {'id': TG_ID},
        }}, format='json', HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=SECRET)

    def flags(self):
        row = NotificationSettings.objects.get(user=self.user)
        return [getattr(row, f) for f in NotificationSettings.FLAGS]

    def test_stop_and_start(self):
        self.assertIn('выключены', self.command('/stop').json()['text'])
        self.assertEqual(self.flags(), [False] * 4)
        # No plan yet: /start explains instead of switching reports on.
        self.assertIn('тренер составит',
                      self.command('/start').json()['text'])
        self.assertEqual(self.flags(), [False] * 4)

    def test_blocking_switches_everything_off(self):
        self.client.post(WEBHOOK_URL, {'update_id': 2, 'my_chat_member': {
            'chat': {'id': TG_ID, 'type': 'private'},
            'new_chat_member': {'status': 'kicked'},
        }}, format='json', HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=SECRET)
        self.assertEqual(self.flags(), [False] * 4)
        self.assertFalse(TelegramAccount.objects.get().can_write)

    def test_stop_when_not_linked(self):
        TelegramAccount.objects.all().delete()
        self.assertIn('Black Fox Nutrition',
                      self.command('/stop').json()['text'])
