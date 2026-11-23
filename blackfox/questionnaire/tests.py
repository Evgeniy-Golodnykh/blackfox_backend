from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from questionnaire.models import Questionnaire
from questionnaire.notifications import build_message
from questionnaire.tokens import hash_claim_token

User = get_user_model()

URL = '/api/questionnaire/'
CLAIM_URL = '/api/questionnaire/claim/'
MINE_URL = '/api/questionnaire/mine/'

ANSWERS = {
    'full_name': 'Иван Иванов',
    'contact': '@ivan',
    'gender': 'Мужской',
    'weight_now': '72,5',
    'diagnoses': 'Гастрит',
}


def make_user(name, role=User.Roles.USER):
    return User.objects.create_user(
        username=name,
        email=f'{name}@example.com',
        password='Str0ng-pass-123',
        gender=User.Gender.MALE,
        role=role,
    )


class QuestionnaireTestCase(APITestCase):

    def setUp(self):
        cache.clear()  # throttle counters
        self.client_user = make_user('client')
        self.other_user = make_user('other')
        self.coach = make_user('coach', User.Roles.COACH)
        self.admin = make_user('admin', User.Roles.ADMIN)

    def submit(self, **overrides):
        payload = {'version': 2, 'answers': ANSWERS, 'consent': True}
        payload.update(overrides)
        return self.client.post(URL, payload, format='json')


class SubmitTests(QuestionnaireTestCase):

    def test_anonymous_submit_returns_only_id_and_token(self):
        response = self.submit()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.json()), {'id', 'claim_token'})
        questionnaire = Questionnaire.objects.get(pk=response.json()['id'])
        self.assertEqual(questionnaire.answers, ANSWERS)
        self.assertEqual(questionnaire.version, 2)
        self.assertEqual(questionnaire.status, 'new')
        self.assertEqual(questionnaire.note, '')
        self.assertIsNotNone(questionnaire.consent_at)
        self.assertIsNone(questionnaire.user)

    def test_only_the_token_hash_is_stored(self):
        token = self.submit().json()['claim_token']

        questionnaire = Questionnaire.objects.get()
        self.assertNotEqual(questionnaire.claim_token_hash, token)
        self.assertEqual(
            questionnaire.claim_token_hash, hash_claim_token(token),
        )
        self.assertGreater(
            questionnaire.claim_token_expires_at,
            timezone.now() + timedelta(days=29),
        )

    def test_consent_is_required(self):
        self.assertEqual(self.submit(consent=False).status_code, 400)
        response = self.client.post(
            URL, {'version': 2, 'answers': ANSWERS}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Questionnaire.objects.exists())

    def test_answers_shape_is_checked(self):
        bad = [
            [],
            {},
            {'age': 34},
            {'note': 'x' * 5001},
            {f'q{i}': 'a' for i in range(61)},
            {'k' * 65: 'a'},
        ]
        for answers in bad:
            cache.clear()  # more attempts than the throttle allows
            with self.subTest(answers=str(answers)[:40]):
                self.assertEqual(self.submit(answers=answers).status_code, 400)
        self.assertFalse(Questionnaire.objects.exists())

    def test_unknown_version_is_rejected(self):
        self.assertEqual(self.submit(version=0).status_code, 400)
        self.assertEqual(self.submit(version=100).status_code, 400)

    def test_status_and_note_cannot_be_set_on_submit(self):
        self.submit(status='accepted', note='сам себе')

        questionnaire = Questionnaire.objects.get()
        self.assertEqual(questionnaire.status, 'new')
        self.assertEqual(questionnaire.note, '')

    def test_anonymous_submit_is_throttled(self):
        for _ in range(5):
            self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(self.submit().status_code, 429)

    def test_faked_forwarded_for_does_not_dodge_the_throttle(self):
        # nginx appends the real address last; a visitor can only prepend.
        for i in range(5):
            response = self.client.post(
                URL, {'version': 2, 'answers': ANSWERS, 'consent': True},
                format='json', HTTP_X_FORWARDED_FOR=f'10.0.0.{i}, 203.0.113.7',
            )
            self.assertEqual(response.status_code, 201)
        response = self.client.post(
            URL, {'version': 2, 'answers': ANSWERS, 'consent': True},
            format='json', HTTP_X_FORWARDED_FOR='10.0.0.99, 203.0.113.7',
        )
        self.assertEqual(response.status_code, 429)

    def test_admin_reads_are_not_throttled(self):
        for _ in range(5):
            self.submit()
        self.client.force_authenticate(self.admin)
        for _ in range(10):
            self.assertEqual(self.client.get(URL).status_code, 200)


class AdminTests(QuestionnaireTestCase):

    def setUp(self):
        super().setUp()
        self.first = Questionnaire.objects.create(
            version=1, answers={'full_name': 'Первая'},
            consent_at=timezone.now(),
        )
        self.second = Questionnaire.objects.create(
            version=2, answers=ANSWERS, consent_at=timezone.now(),
            user=self.client_user,
        )

    def test_only_admin_can_read(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
        for user in (self.client_user, self.coach):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(URL).status_code, 403)
            self.assertEqual(
                self.client.get(f'{URL}{self.first.pk}/').status_code, 403,
            )

    def test_list_is_a_plain_array_newest_first(self):
        self.client.force_authenticate(self.admin)
        data = self.client.get(URL).json()

        self.assertIsInstance(data, list)
        self.assertEqual(
            [q['id'] for q in data], [self.second.pk, self.first.pk],
        )
        self.assertEqual(
            set(data[0]),
            {
                'id', 'version', 'answers', 'created_at', 'status', 'note',
                'user', 'stage', 'reason', 'coach', 'archived',
                'stage_changed_at', 'from_telegram', 'project',
            },
        )
        self.assertEqual(data[0]['answers'], ANSWERS)
        self.assertEqual(data[0]['user']['username'], 'client')
        self.assertIsNone(data[1]['user'])

    def test_admin_patches_status_and_note_only(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'{URL}{self.first.pk}/',
            {'status': 'accepted', 'note': 'Берём', 'answers': {'x': 'y'},
             'version': 7},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.first.refresh_from_db()
        self.assertEqual(self.first.status, 'accepted')
        self.assertEqual(self.first.note, 'Берём')
        self.assertEqual(self.first.answers, {'full_name': 'Первая'})
        self.assertEqual(self.first.version, 1)
        self.assertEqual(response.json()['status'], 'accepted')

    def test_bad_status_is_rejected(self):
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            f'{URL}{self.first.pk}/', {'status': 'maybe'}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_put_is_not_allowed(self):
        self.client.force_authenticate(self.admin)
        response = self.client.put(
            f'{URL}{self.first.pk}/', {'status': 'accepted'}, format='json',
        )
        self.assertEqual(response.status_code, 405)

    def test_others_cannot_patch(self):
        self.client.force_authenticate(self.coach)
        response = self.client.patch(
            f'{URL}{self.first.pk}/', {'status': 'accepted'}, format='json',
        )
        self.assertEqual(response.status_code, 403)


class ClaimAndMineTests(QuestionnaireTestCase):

    def setUp(self):
        super().setUp()
        self.token = self.submit().json()['claim_token']
        self.questionnaire = Questionnaire.objects.get()

    def claim(self, user, token=None):
        self.client.force_authenticate(user)
        return self.client.post(
            CLAIM_URL, {'claim_token': token or self.token}, format='json',
        )

    def test_client_claims_with_the_token(self):
        response = self.claim(self.client_user)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'id': self.questionnaire.pk})
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.user, self.client_user)
        self.assertEqual(self.questionnaire.claim_token_hash, '')
        self.assertIsNone(self.questionnaire.claim_token_expires_at)

    def test_token_works_once(self):
        self.claim(self.client_user)
        self.assertEqual(self.claim(self.other_user).status_code, 400)
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.user, self.client_user)

    def test_wrong_or_expired_token_is_rejected(self):
        self.assertEqual(
            self.claim(self.client_user, 'not-the-token').status_code, 400,
        )
        Questionnaire.objects.update(
            claim_token_expires_at=timezone.now() - timedelta(seconds=1),
        )
        self.assertEqual(self.claim(self.client_user).status_code, 400)
        self.questionnaire.refresh_from_db()
        self.assertIsNone(self.questionnaire.user)

    def test_only_signed_in_clients_can_claim(self):
        response = self.client.post(
            CLAIM_URL, {'claim_token': self.token}, format='json',
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.claim(self.coach).status_code, 403)
        self.questionnaire.refresh_from_db()
        self.assertIsNone(self.questionnaire.user)

    def test_mine_is_404_until_claimed(self):
        self.client.force_authenticate(self.client_user)
        self.assertEqual(self.client.get(MINE_URL).status_code, 404)

    def test_mine_returns_answers_without_admin_fields(self):
        self.claim(self.client_user)
        data = self.client.get(MINE_URL).json()

        self.assertEqual(
            set(data), {'id', 'version', 'answers', 'created_at'},
        )
        self.assertEqual(data['answers'], ANSWERS)

    def test_mine_is_the_latest_and_only_your_own(self):
        self.claim(self.client_user)
        newer = Questionnaire.objects.create(
            version=2, answers={'full_name': 'Новая'},
            consent_at=timezone.now(), user=self.client_user,
        )
        self.assertEqual(self.client.get(MINE_URL).json()['id'], newer.pk)

        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.client.get(MINE_URL).status_code, 404)

    def test_mine_needs_a_login(self):
        self.assertEqual(self.client.get(MINE_URL).status_code, 401)


@override_settings(APP_BASE_URL='https://example.test/')
class NotificationTests(QuestionnaireTestCase):

    def test_message_has_name_contact_and_link_but_no_answers(self):
        questionnaire = Questionnaire.objects.create(
            version=2, answers=ANSWERS, consent_at=timezone.now(),
        )
        text = build_message(questionnaire)

        self.assertIn('Иван Иванов', text)
        self.assertIn('@ivan', text)
        self.assertIn(
            f'https://example.test/applications/{questionnaire.pk}', text,
        )
        self.assertNotIn('Гастрит', text)
        self.assertNotIn('72,5', text)

    @override_settings(TELEGRAM_BOT_TOKEN='', TELEGRAM_NOTIFY_CHAT_ID='')
    def test_submit_works_without_telegram(self):
        with mock.patch('questionnaire.notifications.requests.post') as post:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.submit()
        self.assertEqual(response.status_code, 201)
        post.assert_not_called()

    @override_settings(TELEGRAM_BOT_TOKEN='t', TELEGRAM_NOTIFY_CHAT_ID='1')
    def test_telegram_failure_does_not_break_submit(self):
        with mock.patch(
            'questionnaire.notifications.threading.Thread',
        ) as thread, mock.patch(
            'questionnaire.notifications.requests.post',
            side_effect=OSError('down'),
        ) as post:
            # Run the background send inline.
            thread.side_effect = lambda target, daemon: mock.Mock(
                start=target,
            )
            with self.captureOnCommitCallbacks(execute=True):
                response = self.submit()

        self.assertEqual(response.status_code, 201)
        post.assert_called_once()
        self.assertNotIn('Гастрит', post.call_args.kwargs['json']['text'])


class InviteTests(QuestionnaireTestCase):

    def setUp(self):
        super().setUp()
        self.questionnaire = Questionnaire.objects.create(
            version=2, answers=ANSWERS, consent_at=timezone.now(),
        )
        self.url = f'{URL}{self.questionnaire.pk}/invite/'

    def test_admin_gets_a_link_that_claims_the_application(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        link = response.json()['url']
        self.assertIn('/signup?from=invite&claim=', link)
        token = link.split('claim=')[1]

        self.client.force_authenticate(self.client_user)
        claimed = self.client.post(CLAIM_URL, {'claim_token': token},
                                   format='json')
        self.assertEqual(claimed.status_code, 200)
        self.questionnaire.refresh_from_db()
        self.assertEqual(self.questionnaire.user, self.client_user)

    def test_a_new_invite_replaces_the_old_one(self):
        self.client.force_authenticate(self.admin)
        first = self.client.post(self.url).json()['url'].split('claim=')[1]
        self.client.post(self.url)
        self.client.force_authenticate(self.client_user)
        response = self.client.post(CLAIM_URL, {'claim_token': first},
                                    format='json')
        self.assertEqual(response.status_code, 400)

    def test_only_admin_and_not_when_linked(self):
        for user in (self.client_user, self.coach):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post(self.url).status_code, 403)
        Questionnaire.objects.filter(pk=self.questionnaire.pk).update(
            user=self.client_user)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(self.url).status_code, 400)
