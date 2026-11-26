from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from checkins.models import DailyCheckin
from coaching.models import CoachClient, CoachInvite
from questionnaire.models import Questionnaire
from tgbot.models import TelegramAccount
from training.models import BodyStatsDiary, FoodDiary, Project

User = get_user_model()


def make(name, role=User.Roles.USER, **extra):
    return User.objects.create_user(
        username=name, email=f'{name}@example.com', password='Str0ng-pass-1',
        gender=User.Gender.FEMALE, role=role, first_name=name.title(),
        **extra,
    )


def project_for(user, coach):
    return Project.objects.create(
        user=user, coach=coach, start_date=date.today(), start_weight=84,
        target_weight=75, target_calories=2000, target_carbohydrate=200,
        target_fat=70, target_fiber=25, target_protein=140, target_sugar=50,
    )


PROJECT = {
    'start_date': str(date.today()), 'start_weight': 84, 'target_weight': 75,
    'target_calories': 2000, 'target_carbohydrate': 200, 'target_fat': 70,
    'target_fiber': 25, 'target_protein': 140, 'target_sugar': 50,
}


@mock.patch('coaching.views.notify_coach_of_new_client')
class InviteAndJoinTests(APITestCase):

    def setUp(self):
        self.fox = make('fox', User.Roles.COACH)
        self.wolf = make('wolf', User.Roles.COACH)
        self.anna = make('anna')

    def code(self, coach):
        self.client.force_authenticate(coach)
        return self.client.get('/api/coach/invite/').json()['code']

    def join(self, user, code):
        self.client.force_authenticate(user)
        return self.client.post('/api/coach/join/', {'code': code},
                                format='json')

    def test_coach_gets_a_link_and_can_replace_it(self, _):
        self.client.force_authenticate(self.fox)
        first = self.client.get('/api/coach/invite/').json()
        self.assertTrue(first['url'].endswith(f"/join/{first['code']}"))
        self.assertIn(f"start=join_{first['code']}", first['bot_url'])
        self.assertEqual(self.client.get('/api/coach/invite/').json()['code'],
                         first['code'])
        second = self.client.post('/api/coach/invite/').json()
        self.assertNotEqual(second['code'], first['code'])
        self.assertEqual(self.join(self.anna, first['code']).status_code, 400)

    def test_clients_get_no_link(self, _):
        self.client.force_authenticate(self.anna)
        self.assertEqual(self.client.get('/api/coach/invite/').status_code,
                         403)

    def test_public_card_has_no_private_data(self, _):
        code = self.code(self.fox)
        self.client.force_authenticate(None)
        card = self.client.get(f'/api/coach/invite/{code}/').json()
        self.assertEqual(card['first_name'], 'Fox')
        self.assertNotIn('email', card)
        self.assertEqual(
            self.client.get('/api/coach/invite/nope/').status_code, 404)

    def test_client_joins_once_and_coach_is_told(self, notify):
        code = self.code(self.fox)
        response = self.join(self.anna, code)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['joined'])
        self.assertEqual(CoachClient.objects.get().coach, self.fox)
        notify.assert_called_once_with(self.fox, self.anna)
        again = self.join(self.anna, code)
        self.assertFalse(again.json()['joined'])
        self.assertEqual(notify.call_count, 1)
        self.client.force_authenticate(self.anna)
        self.assertEqual(self.client.get('/api/users/me/').json()['coach'],
                         'fox')

    def test_another_coach_is_refused(self, _):
        self.join(self.anna, self.code(self.fox))
        self.assertEqual(self.join(self.anna, self.code(self.wolf))
                         .status_code, 409)
        olga = make('olga')
        project_for(olga, self.wolf)
        self.assertEqual(self.join(olga, self.code(self.fox)).status_code,
                         409)

    def test_only_clients_join(self, _):
        code = self.code(self.fox)
        self.assertEqual(self.join(self.wolf, code).status_code, 403)


class ClientsListTests(APITestCase):

    def setUp(self):
        self.fox = make('fox', User.Roles.COACH)
        self.wolf = make('wolf', User.Roles.COACH)
        self.anna = make('anna')      # fox, with a plan
        self.olga = make('olga')      # fox, joined, waiting
        self.ivan = make('ivan')      # wolf's
        project_for(self.anna, self.fox)
        CoachClient.objects.create(client=self.olga, coach=self.fox)
        project_for(self.ivan, self.wolf)
        self.application = Questionnaire.objects.create(
            version=2, answers={'full_name': 'Olga'},
            consent_at=timezone.now(), user=self.olga,
        )

    def test_my_clients_with_status_and_questionnaire(self):
        self.client.force_authenticate(self.fox)
        rows = self.client.get('/api/coach/clients/').json()
        by_name = {r['username']: r for r in rows}
        self.assertEqual(set(by_name), {'anna', 'olga'})
        self.assertEqual(by_name['anna']['status'], 'active')
        self.assertEqual(by_name['olga']['status'], 'waiting')
        self.assertEqual(by_name['olga']['questionnaire'],
                         self.application.pk)
        self.assertEqual(rows[0]['username'], 'olga')  # waiting first
        self.assertNotIn('email', rows[0])

    def test_coach_reads_own_clients_questionnaire_only(self):
        self.client.force_authenticate(self.fox)
        ok = self.client.get('/api/coach/clients/olga/questionnaire/')
        self.assertEqual(ok.json()['answers'], {'full_name': 'Olga'})
        self.client.force_authenticate(self.wolf)
        self.assertEqual(
            self.client.get('/api/coach/clients/olga/questionnaire/')
            .status_code, 403)

    def test_public_coach_list(self):
        self.client.force_authenticate(None)
        rows = {r['username']: r for r in
                self.client.get('/api/coaches/').json()}
        self.assertEqual(set(rows), {'fox', 'wolf'})
        self.assertEqual(rows['fox']['clients_count'], 2)
        self.assertEqual(rows['wolf']['clients_count'], 1)
        self.assertNotIn('email', rows['fox'])


class PrivacyTests(APITestCase):
    """A coach sees their own clients' data and nobody else's."""

    def setUp(self):
        self.fox = make('fox', User.Roles.COACH)
        self.wolf = make('wolf', User.Roles.COACH)
        self.admin = make('boss', User.Roles.ADMIN)
        self.anna = make('anna')
        self.olga = make('olga')
        self.ivan = make('ivan')
        project_for(self.anna, self.fox)
        CoachClient.objects.create(client=self.olga, coach=self.fox)
        project_for(self.ivan, self.wolf)
        for user in (self.anna, self.olga, self.ivan):
            FoodDiary.objects.create(
                user=user, date=date.today(), calories_actual=1800,
                calories_target=2000, protein_actual=120, protein_target=140,
                fat_actual=60, fat_target=70, carbohydrate_actual=200,
                carbohydrate_target=210, fiber_actual=20, fiber_target=25,
                sugar_actual=30, sugar_target=50, weight_actual=80,
                weight_target=75,
            )
            BodyStatsDiary.objects.create(user=user, date=date.today(),
                                          waist=80)
            DailyCheckin.objects.create(user=user, date=date.today(),
                                        sleep=3, wellbeing=3, stress=3,
                                        hunger=3)

    def users_in(self, url):
        data = self.client.get(url).json()
        return sorted({row['user']['username'] if isinstance(row['user'],
                                                             dict)
                       else row['user'] for row in data})

    def test_coach_sees_only_own_clients_data(self):
        self.client.force_authenticate(self.fox)
        self.assertEqual(self.users_in('/api/fooddiary/'), ['anna', 'olga'])
        self.assertEqual(self.users_in('/api/bodystats/'), ['anna', 'olga'])
        self.assertEqual(
            self.client.get('/api/checkins/', {'user': 'ivan'}).status_code,
            403)
        self.assertEqual(
            self.client.get('/api/checkins/', {'user': 'olga'}).status_code,
            200)

    def test_users_list_is_scoped(self):
        self.client.force_authenticate(self.fox)
        names = {u['username'] for u in self.client.get('/api/users/').json()}
        self.assertEqual(names, {'fox', 'anna', 'olga'})
        self.client.force_authenticate(self.anna)
        # Clients can't list users at all; reading someone else's profile
        # by id finds nothing.
        self.assertEqual(self.client.get('/api/users/').status_code, 403)
        response = self.client.get(f'/api/users/{self.ivan.pk}/')
        self.assertEqual(response.status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self.client.get('/api/users/').json()), 6)

    def test_coach_writes_only_for_own_clients(self):
        self.client.force_authenticate(self.fox)
        yesterday = str(date.today() - timedelta(days=1))
        ok = self.client.post('/api/bodystats/?user=olga',
                              {'date': yesterday, 'waist': 79},
                              format='json')
        self.assertIn(ok.status_code, (200, 201))
        refused = self.client.post('/api/bodystats/?user=ivan',
                                   {'date': yesterday, 'waist': 79},
                                   format='json')
        self.assertEqual(refused.status_code, 403)

    def test_coach_plans_for_own_joined_client_only(self):
        self.client.force_authenticate(self.fox)
        ok = self.client.post('/api/project/', {**PROJECT, 'user': 'olga',
                                                'coach': 'fox'},
                              format='json')
        self.assertEqual(ok.status_code, 201, ok.content)
        stranger = make('pete')
        refused = self.client.post('/api/project/', {**PROJECT,
                                                     'user': 'pete',
                                                     'coach': 'fox'},
                                   format='json')
        self.assertEqual(refused.status_code, 403)
        self.assertFalse(Project.objects.filter(user=stranger).exists())
        as_other = self.client.post('/api/project/', {**PROJECT,
                                                      'user': 'olga',
                                                      'coach': 'wolf'},
                                    format='json')
        self.assertIn(as_other.status_code, (400, 403))


class CyclePrivacyTests(APITestCase):
    """Cycle data is written for oneself or by one's own coach only."""

    SETTINGS = {'cycle_length_days': 28, 'period_length_days': 5}

    def setUp(self):
        self.fox = make('fox', User.Roles.COACH)
        self.anna = make('anna')     # fox's
        self.olga = make('olga')     # nobody's
        project_for(self.anna, self.fox)

    def post(self, viewer, url, data):
        self.client.force_authenticate(viewer)
        return self.client.post(url, data, format='json')

    def test_client_writes_only_her_own(self):
        own = self.post(self.anna, '/api/cycle/settings/',
                        {'user': 'anna', **self.SETTINGS})
        self.assertEqual(own.status_code, 201, own.content)
        for url, data in (
            ('/api/cycle/settings/', self.SETTINGS),
            ('/api/cycle/periods/', {'date': str(date.today())}),
            ('/api/cycle/overrides/', {'date': str(date.today()),
                                       'phase': 'luteal'}),
        ):
            response = self.post(self.anna, url, {'user': 'olga', **data})
            self.assertEqual(response.status_code, 400, url)
        from cycles.models import CycleSettings, PeriodEntry, PhaseOverride
        for model in (CycleSettings, PeriodEntry, PhaseOverride):
            self.assertFalse(model.objects.filter(user=self.olga).exists())

    def test_coach_writes_for_own_client_only(self):
        ok = self.post(self.fox, '/api/cycle/settings/',
                       {'user': 'anna', **self.SETTINGS})
        self.assertEqual(ok.status_code, 201, ok.content)
        refused = self.post(self.fox, '/api/cycle/settings/',
                            {'user': 'olga', **self.SETTINGS})
        self.assertEqual(refused.status_code, 400)


@override_settings(TELEGRAM_BOT_TOKEN='1:x', TELEGRAM_WEBHOOK_SECRET='s',
                   APP_BASE_URL='https://app.example.test')
@mock.patch('coaching.services.notify_coach_of_new_client')
class BotJoinTests(APITestCase):

    def setUp(self):
        self.fox = make('fox', User.Roles.COACH)
        self.invite = CoachInvite.objects.create(coach=self.fox)
        self.anna = make('anna')

    def start(self, text, tg_id=42):
        return self.client.post('/api/telegram/webhook/', {
            'update_id': 1, 'message': {
                'text': text, 'chat': {'id': tg_id, 'type': 'private'},
                'from': {'id': tg_id}},
        }, format='json', HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN='s').json()

    def test_linked_client_joins_from_the_bot(self, _):
        TelegramAccount.objects.create(user=self.anna, telegram_id=42)
        body = self.start(f'/start join_{self.invite.code}')
        self.assertIn('вы у тренера Fox', body['text'])
        self.assertIn('Осталась анкета', body['text'])
        url = body['reply_markup']['inline_keyboard'][0][0]['web_app']['url']
        self.assertTrue(url.endswith('/questionnaire'))
        self.assertEqual(CoachClient.objects.get().client, self.anna)

    def test_client_with_questionnaire_just_waits(self, _):
        TelegramAccount.objects.create(user=self.anna, telegram_id=42)
        Questionnaire.objects.create(version=2, answers={},
                                     consent_at=timezone.now(),
                                     user=self.anna)
        body = self.start(f'/start join_{self.invite.code}')
        self.assertIn('напишу, когда он будет готов', body['text'])

    def test_unknown_telegram_goes_to_the_join_page(self, _):
        body = self.start(f'/start join_{self.invite.code}')
        url = body['reply_markup']['inline_keyboard'][0][0]['web_app']['url']
        self.assertEqual(url, f'https://app.example.test/join/'
                              f'{self.invite.code}')
        self.assertFalse(CoachClient.objects.exists())


@override_settings(TELEGRAM_NOTIFY_CHAT_ID='-100', TELEGRAM_BOT_TOKEN='1:x',
                   APP_BASE_URL='https://app.example.test')
@mock.patch('tgbot.telegram_api.send_message', return_value='sent')
class NewClientNoticeTests(APITestCase):

    def setUp(self):
        from datetime import timedelta as td
        self.fox = make('fox', User.Roles.COACH)
        self.hour_ago = timezone.now() - td(hours=1)

    def joined(self, name, **extra):
        user = make(name, **extra)
        User.objects.filter(pk=user.pk).update(date_joined=self.hour_ago)
        return user

    def test_admin_told_once_about_a_client_without_anything(self, send):
        from coaching.notices import announce_new_clients
        lone = self.joined('lone')
        with_app = self.joined('withapp')
        Questionnaire.objects.create(version=2, answers={},
                                     consent_at=timezone.now(), user=with_app)
        with_coach = self.joined('withcoach')
        CoachClient.objects.create(client=with_coach, coach=self.fox)
        make('fresh')  # signed up a minute ago: the claim may still come
        inactive = self.joined('inactive')
        User.objects.filter(pk=inactive.pk).update(is_active=False)

        self.assertEqual(announce_new_clients(), 1)
        text = send.call_args[0][1]
        self.assertIn('@lone', text)
        self.assertIn('/users/lone', text)
        self.assertEqual(announce_new_clients(), 0)  # only once
        self.assertTrue(lone.new_client_notice)


@mock.patch('coaching.services.notify_coach_of_assigned_client')
class AdminAssignTests(APITestCase):

    def setUp(self):
        self.fox = make('fox', User.Roles.COACH)
        self.wolf = make('wolf', User.Roles.COACH)
        self.admin = make('boss', User.Roles.ADMIN)
        self.anna = make('anna')

    def assign(self, client, coach, as_user=None):
        self.client.force_authenticate(as_user or self.admin)
        return self.client.post('/api/coach/assign/',
                                {'client': client, 'coach': coach},
                                format='json')

    def test_admin_assigns_and_reassigns(self, notify):
        self.assertTrue(self.assign('anna', 'fox').json()['changed'])
        notify.assert_called_once_with(self.fox, self.anna)
        self.assertFalse(self.assign('anna', 'fox').json()['changed'])
        self.assign('anna', 'wolf')
        self.assertEqual(CoachClient.objects.get(client=self.anna).coach,
                         self.wolf)
        self.client.force_authenticate(self.anna)
        self.assertEqual(self.client.get('/api/users/me/').json()['coach'],
                         'wolf')

    def test_refused_when_another_coach_leads_the_plan(self, _):
        project_for(self.anna, self.wolf)
        self.assertEqual(self.assign('anna', 'fox').status_code, 409)

    def test_only_admin_and_real_people(self, _):
        self.assertEqual(self.assign('anna', 'fox', self.fox).status_code,
                         403)
        self.assertEqual(self.assign('anna', 'boss').status_code, 400)
        self.assertEqual(self.assign('nobody', 'fox').status_code, 400)
