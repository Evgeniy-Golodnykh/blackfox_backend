from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from tgbot.models import NotificationSettings, TelegramAccount
from tgbot.tests import BOT_TOKEN, SECRET, TG_ID, WEBHOOK_URL, make_init_data
from training.models import Project

User = get_user_model()


def make_user(name, role=User.Roles.USER, fatsecret=True):
    return User.objects.create_user(
        username=name, email=f'{name}@example.com', password='Str0ng-pass-1',
        gender=User.Gender.FEMALE, role=role, first_name='Анна',
        fatsecret_token='t' if fatsecret else None,
        fatsecret_secret='s' if fatsecret else None,
    )


def make_project(user):
    coach = make_user(f'{user.username}-coach', User.Roles.COACH)
    return Project.objects.create(
        user=user, coach=coach, start_date=date.today(), start_weight=84,
        target_weight=75, target_calories=2000, target_carbohydrate=200,
        target_fat=70, target_fiber=25, target_protein=140, target_sugar=50,
    )


def flags(user):
    prefs = NotificationSettings.objects.get(user=user)
    return [getattr(prefs, f) for f in NotificationSettings.FLAGS]


def buttons(body):
    return [b for row in body['reply_markup']['inline_keyboard'] for b in row]


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN,
                   TELEGRAM_WEBHOOK_SECRET=SECRET)
class OnboardingTests(APITestCase):

    def setUp(self):
        self.user = make_user('anna')

    def post(self, update):
        return self.client.post(WEBHOOK_URL, update, format='json',
                                HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=SECRET)

    def say(self, text):
        return self.post({'update_id': 1, 'message': {
            'text': text, 'chat': {'id': TG_ID, 'type': 'private'},
            'from': {'id': TG_ID},
        }}).json()

    def tap_enable(self):
        return self.post({'update_id': 2, 'callback_query': {
            'id': '77', 'data': 'enable_reports', 'from': {'id': TG_ID},
        }}).json()

    def link_from_app(self):
        self.client.force_authenticate(self.user)
        try:
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.post('/api/users/me/telegram/',
                                        {'init_data': make_init_data()},
                                        format='json').status_code
        finally:
            self.client.force_authenticate(None)

    def test_welcome_for_strangers(self):
        body = self.say('/start')
        self.assertIn('Black Fox Nutrition', body['text'])
        urls = [b['web_app']['url'] for b in buttons(body)]
        self.assertTrue(urls[0].endswith('/login'))
        self.assertTrue(urls[1].endswith('/questionnaire'))
        self.assertIn('/help', self.say('что ты умеешь?')['text'])

    @mock.patch('tgbot.onboarding.threading.Thread')
    def test_first_link_switches_reports_off_and_says_hello(self, thread):
        self.assertEqual(self.link_from_app(), 204)
        self.assertEqual(flags(self.user), [False] * 4)
        thread.assert_called_once()
        # A second login inside Telegram doesn't greet again.
        thread.reset_mock()
        self.link_from_app()
        thread.assert_not_called()

    def test_linked_message_without_a_plan(self):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        NotificationSettings.objects.create(
            user=self.user, **{f: False for f in NotificationSettings.FLAGS})
        body = self.say('/start')
        self.assertIn('когда тренер составит ваш план', body['text'])
        self.assertNotIn('enable_reports', str(body))
        self.assertEqual(flags(self.user), [False] * 4)

    @mock.patch('tgbot.views.send_message')
    def test_enable_button(self, send):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        make_project(self.user)
        NotificationSettings.objects.create(
            user=self.user, **{f: False for f in NotificationSettings.FLAGS})
        from tgbot.onboarding import linked
        text, markup = linked(self.user)
        self.assertIn('включить отчёты?', text)
        self.assertIn('enable_reports', str(markup))

        answer = self.tap_enable()

        self.assertEqual(answer['method'], 'answerCallbackQuery')
        self.assertEqual(answer['callback_query_id'], '77')
        self.assertEqual(flags(self.user), [True] * 4)
        self.assertIn('Отчёты включены', send.call_args.args[1])

    def test_start_with_a_plan_turns_reports_on(self):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        make_project(self.user)
        body = self.say('/start')
        self.assertIn('Отчёты включены', body['text'])
        self.assertEqual(flags(self.user), [True] * 4)

    def test_help_and_fatsecret_hint(self):
        nofs = make_user('olga', fatsecret=False)
        TelegramAccount.objects.create(user=nofs, telegram_id=TG_ID)
        body = self.say('/help')
        self.assertIn('/stop', body['text'])
        from tgbot.onboarding import linked
        text, _ = linked(nofs)
        self.assertIn('FatSecret', text)

    @mock.patch('tgbot.onboarding.threading.Thread')
    def test_plan_ready_message(self, thread):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        NotificationSettings.objects.create(
            user=self.user, **{f: False for f in NotificationSettings.FLAGS})
        with self.captureOnCommitCallbacks(execute=True):
            make_project(self.user)
        thread.assert_called_once()

    @mock.patch('tgbot.onboarding.threading.Thread')
    def test_no_plan_message_when_reports_are_on_or_not_linked(self, thread):
        with self.captureOnCommitCallbacks(execute=True):
            make_project(self.user)  # not linked
        other = make_user('olga')
        TelegramAccount.objects.create(user=other, telegram_id=TG_ID)
        NotificationSettings.objects.create(user=other)  # defaults: on
        with self.captureOnCommitCallbacks(execute=True):
            make_project(other)
        thread.assert_not_called()
