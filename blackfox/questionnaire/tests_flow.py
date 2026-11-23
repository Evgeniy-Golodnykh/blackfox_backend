from datetime import date, timedelta
from unittest import mock

from django.test import override_settings
from django.utils import timezone

from coaching.models import CoachClient
from questionnaire import flow
from questionnaire.models import ApplicationProgress, Questionnaire
from questionnaire.notifications import applicant_reply
from questionnaire.tests import ANSWERS, URL, QuestionnaireTestCase
from tgbot.tests import BOT_TOKEN, TG_ID, make_init_data
from training.models import Project

Stage = ApplicationProgress.Stage


def make_application(user=None, days_ago=0, **extra):
    application = Questionnaire.objects.create(
        version=2, answers=ANSWERS, consent_at=timezone.now(), user=user,
        **extra,
    )
    if days_ago:
        Questionnaire.objects.filter(pk=application.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago))
        application.refresh_from_db()
    return application


def make_project(user, coach):
    return Project.objects.create(
        user=user, coach=coach, start_date=date.today(), start_weight=84,
        target_weight=75, target_calories=2000, target_carbohydrate=200,
        target_fat=70, target_fiber=25, target_protein=140, target_sugar=50,
    )


@mock.patch('questionnaire.flow.notify_coach_of_application')
class StageTests(QuestionnaireTestCase):

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin)

    def patch(self, application, **data):
        return self.client.patch(f'{URL}{application.pk}/', data,
                                 format='json')

    def test_new_by_default_and_contacted_with_a_note(self, _):
        application = make_application()
        row = self.client.get(f'{URL}{application.pk}/').json()
        self.assertEqual(row['stage'], 'new')
        response = self.patch(application, stage='contacted',
                              note='Созвонились, ждёт тренера')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['stage'], 'contacted')
        self.assertEqual(response.json()['note'], 'Созвонились, ждёт тренера')
        self.assertIsNotNone(application.progress.first_response_at)

    def test_decline_needs_a_reason(self, _):
        application = make_application()
        self.assertEqual(self.patch(application, stage='declined')
                         .status_code, 400)
        response = self.patch(application, stage='no_answer',
                              reason='Не отвечает 3 дня')
        self.assertEqual(response.json()['reason'], 'Не отвечает 3 дня')
        application.refresh_from_db()
        self.assertEqual(application.status, 'declined')  # old field in step

    def test_assigned_and_active_are_not_set_by_hand(self, _):
        application = make_application()
        self.assertEqual(self.patch(application, stage='active').status_code,
                         400)

    def test_archive_after_30_days(self, _):
        old = make_application()
        flow.set_stage(old, Stage.DECLINED, reason='Дорого',
                       now=timezone.now() - timedelta(days=31))
        fresh = make_application()
        ids = [r['id'] for r in self.client.get(URL).json()]
        self.assertEqual(ids, [fresh.pk])
        archived = self.client.get(URL, {'archived': 1}).json()
        self.assertEqual([r['id'] for r in archived], [old.pk])
        self.assertTrue(archived[0]['archived'])

    def test_assign_coach_of_a_linked_client(self, notify):
        application = make_application(user=self.client_user)
        response = self.client.post(f'{URL}{application.pk}/assign/',
                                    {'coach': 'coach'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['stage'], 'assigned')
        self.assertEqual(response.json()['coach']['username'], 'coach')
        link = CoachClient.objects.get(client=self.client_user)
        self.assertEqual(link.coach, self.coach)
        notify.assert_called_once()

    def test_assign_refused_when_another_coach_has_the_plan(self, _):
        other = self.make_coach('wolf')
        make_project(self.client_user, other)
        application = make_application(user=self.client_user)
        response = self.client.post(f'{URL}{application.pk}/assign/',
                                    {'coach': 'coach'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.post(
            f'{URL}{application.pk}/assign/', {'coach': 'client'},
            format='json').status_code, 400)

    def test_plan_makes_it_active(self, _):
        application = make_application(user=self.client_user)
        flow.assign_coach(application, self.coach)
        make_project(self.client_user, self.coach)
        application.refresh_from_db()
        self.assertEqual(flow.stage_of(application), Stage.ACTIVE)
        self.assertIsNotNone(application.progress.active_at)
        self.assertEqual(application.status, 'accepted')

    def test_sign_up_later_goes_to_the_assigned_coach(self, _):
        application = make_application()
        flow.assign_coach(application, self.coach)
        token = self.client.post(f'{URL}{application.pk}/invite/').json()[
            'url'].split('claim=')[1]
        self.client.force_authenticate(self.client_user)
        response = self.client.post(f'{URL}claim/', {'claim_token': token},
                                    format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(CoachClient.objects.get(client=self.client_user)
                         .coach, self.coach)

    def test_only_admin(self, _):
        application = make_application()
        self.client.force_authenticate(self.coach)
        self.assertEqual(self.client.post(f'{URL}{application.pk}/assign/',
                                          {'coach': 'coach'}, format='json')
                         .status_code, 403)
        self.assertEqual(self.client.get(f'{URL}funnel/').status_code, 403)

    def make_coach(self, name):
        from questionnaire.tests import make_user
        return make_user(name, self.coach.Roles.COACH)


@mock.patch('questionnaire.flow.notify_coach_of_application')
class CoachApplicationsTests(QuestionnaireTestCase):

    def test_coach_sees_only_assigned_unlinked_ones(self, _):
        mine = make_application()
        flow.assign_coach(mine, self.coach)
        make_application()  # not assigned
        linked = make_application(user=self.client_user)
        flow.assign_coach(linked, self.coach)  # in «Мои клиенты» instead
        self.client.force_authenticate(self.coach)
        rows = self.client.get('/api/coach/applications/').json()
        self.assertEqual([r['id'] for r in rows], [mine.pk])
        self.assertEqual(rows[0]['contact'], '@ivan')
        self.assertNotIn('answers', rows[0])
        detail = self.client.get(f'/api/coach/applications/{mine.pk}/')
        self.assertEqual(detail.json()['answers']['diagnoses'], 'Гастрит')
        invite = self.client.post(
            f'/api/coach/applications/{mine.pk}/invite/')
        self.assertIn('claim=', invite.json()['url'])

    def test_other_coach_cannot_open_it(self, _):
        from questionnaire.tests import make_user
        wolf = make_user('wolf', self.coach.Roles.COACH)
        application = make_application()
        flow.assign_coach(application, self.coach)
        self.client.force_authenticate(wolf)
        self.assertEqual(self.client.get(
            f'/api/coach/applications/{application.pk}/').status_code, 404)


@override_settings(TELEGRAM_NOTIFY_CHAT_ID='-100',
                   TELEGRAM_BOT_TOKEN=BOT_TOKEN,
                   APP_BASE_URL='https://app.example.test')
class ReminderTests(QuestionnaireTestCase):

    @mock.patch('tgbot.telegram_api.send_message', return_value='sent')
    def test_admin_reminded_once_about_day_old_new_ones(self, send):
        stale = make_application(days_ago=2)
        make_application()  # fresh
        make_application(days_ago=30)  # too old to nag about
        handled = make_application(days_ago=2)
        flow.set_stage(handled, Stage.CONTACTED)
        self.assertEqual(flow.remind_admin(), 1)
        text = send.call_args[0][1]
        self.assertIn(f'№{stale.pk}', text)
        self.assertNotIn('Гастрит', text)  # never health data
        self.assertEqual(flow.remind_admin(), 0)


@override_settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN)
class AutoreplyTests(QuestionnaireTestCase):

    @mock.patch('questionnaire.serializers.reply_to_applicant')
    @mock.patch('questionnaire.serializers.notify_new_questionnaire')
    def test_mini_app_sender_gets_an_answer(self, _, reply):
        plan = {'calories': 1750, 'protein': 126, 'fat': 70, 'carbs': 160}
        with self.captureOnCommitCallbacks(execute=True):
            response = self.submit(tg_init_data=make_init_data(), plan=plan)
        self.assertEqual(response.status_code, 201, response.content)
        application = Questionnaire.objects.get()
        self.assertEqual(application.progress.telegram_id, TG_ID)
        reply.assert_called_once()
        self.assertEqual(reply.call_args[0][1], TG_ID)

    @mock.patch('questionnaire.serializers.reply_to_applicant')
    def test_forged_init_data_is_ignored(self, reply):
        response = self.submit(tg_init_data='user=%7B%22id%22%3A1%7D&hash=x')
        self.assertEqual(response.status_code, 201)
        self.assertFalse(ApplicationProgress.objects.exists())
        reply.assert_not_called()

    def test_reply_text(self):
        application = make_application()
        text = applicant_reply(application, {'calories': 1750, 'protein': 126,
                                             'fat': 70, 'carbs': 160})
        self.assertIn('Тренер напишет вам до', text)
        self.assertIn('1750 ккал', text)
        self.assertNotIn('Гастрит', text)


@mock.patch('questionnaire.flow.notify_coach_of_application')
class FunnelTests(QuestionnaireTestCase):

    def test_weekly_counts(self, _):
        a = make_application(user=self.client_user)
        flow.set_stage(a, Stage.CONTACTED,
                       now=a.created_at + timedelta(hours=3))
        flow.assign_coach(a, self.coach)
        make_project(self.client_user, self.coach)
        make_application()
        self.client.force_authenticate(self.admin)
        week = self.client.get(f'{URL}funnel/', {'weeks': 2}).json()[-1]
        self.assertEqual((week['received'], week['contacted'],
                          week['assigned'], week['active']), (2, 1, 1, 1))
        self.assertEqual(week['median_response_hours'], 3.0)
        self.assertIsNone(week['paid'])
