from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APITestCase

from activity.models import ActivityDay
from activity.sync import sync_activity
from training.models import Project

User = get_user_model()

URL = '/api/activity/'
TODAY = date(2026, 11, 22)


def make_user(name, role=User.Roles.USER, fatsecret=True):
    return User.objects.create_user(
        username=name, email=f'{name}@example.com', password='Str0ng-pass-1',
        gender=User.Gender.MALE, role=role,
        fatsecret_token='t' if fatsecret else None,
        fatsecret_secret='s' if fatsecret else None,
    )


def month(*days):
    """A get_month.v2 answer: (date, kcal) pairs."""

    epoch = date(1970, 1, 1)
    items = [{'date_int': str((d - epoch).days), 'calories': str(k)}
             for d, k in days]
    return {'month': {'day': items[0] if len(items) == 1 else items}}


class FakeSession:

    def __init__(self, answers):
        self.answers = list(answers)
        self.calls = []

    def get(self, url, params):
        self.calls.append(params)
        answer = self.answers.pop(0)
        return mock.Mock(json=lambda: answer)

    def close(self):
        pass


class SyncTests(APITestCase):

    def setUp(self):
        cache.clear()
        self.user = make_user('nik')

    def run_sync(self, *answers):
        session = FakeSession(answers)
        with mock.patch('fatsecret.tools.fatsecret.get_session',
                        return_value=session):
            saved = sync_activity(self.user, today=TODAY)
        return saved, session

    def test_two_months_saved(self):
        saved, session = self.run_sync(
            month((date(2026, 10, 31), 2100)),
            month((date(2026, 11, 21), 1833.4), (date(2026, 11, 22), 2335)),
        )
        self.assertEqual(saved, 3)
        self.assertEqual(
            [s['method'] for s in session.calls],
            ['exercise_entries.get_month.v2'] * 2,
        )
        self.assertEqual(
            dict(ActivityDay.objects.values_list('date', 'calories_burned')),
            {date(2026, 10, 31): 2100, date(2026, 11, 21): 1833,
             date(2026, 11, 22): 2335},
        )

    def test_resync_updates_and_skips_future(self):
        self.run_sync({'month': {}}, month((TODAY, 1200)))
        self.run_sync({'month': {}}, month((TODAY, 2335),
                                           (date(2026, 11, 23), 999)))
        self.assertEqual(
            list(ActivityDay.objects.values_list('date', 'calories_burned')),
            [(TODAY, 2335)],
        )

    def test_fatsecret_error_saves_nothing(self):
        saved, _ = self.run_sync({'error': {'code': 8, 'message': 'x'}})
        self.assertEqual(saved, 0)
        self.assertFalse(ActivityDay.objects.exists())

    def test_without_fatsecret_nothing_is_asked(self):
        user = make_user('nofs', fatsecret=False)
        with mock.patch('fatsecret.tools.fatsecret.get_session') as get:
            self.assertEqual(sync_activity(user), 0)
        get.assert_not_called()


@mock.patch('activity.views.sync_if_stale')
class EndpointTests(APITestCase):

    def setUp(self):
        self.client_user = make_user('anna')
        self.other = make_user('olga')
        self.coach = make_user('fox', User.Roles.COACH, fatsecret=False)
        Project.objects.create(
            user=self.client_user, coach=self.coach, start_date=TODAY,
            start_weight=84, target_weight=75, target_calories=2000,
            target_carbohydrate=200, target_fat=70, target_fiber=25,
            target_protein=140, target_sugar=50,
        )
        ActivityDay.objects.create(user=self.client_user,
                                   date=date.today(), calories_burned=2335)

    def test_own_days(self, sync):
        self.client.force_authenticate(self.client_user)
        data = self.client.get(URL).json()
        self.assertTrue(data['fatsecret'])
        self.assertEqual(data['days'], [{'date': str(date.today()),
                                         'calories_burned': 2335}])
        sync.assert_called_once()

    def test_who_can_read(self, _):
        for user, expected in ((self.coach, 200), (self.other, 403)):
            self.client.force_authenticate(user)
            response = self.client.get(URL, {'user': 'anna'})
            self.assertEqual(response.status_code, expected)

    def test_needs_a_login(self, _):
        self.assertEqual(self.client.get(URL).status_code, 401)


class StaleTests(APITestCase):

    def test_asks_fatsecret_at_most_every_30_minutes(self):
        cache.clear()
        user = make_user('nik')
        with mock.patch('activity.sync.sync_activity') as sync:
            from activity.sync import sync_if_stale
            sync_if_stale(user)
            sync_if_stale(user)
        sync.assert_called_once()
