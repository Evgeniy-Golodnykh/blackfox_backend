from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from checkins.models import DailyCheckin
from training.models import Project

User = get_user_model()

URL = '/api/checkins/'


def make_user(name, role=User.Roles.USER):
    return User.objects.create_user(
        username=name, email=f'{name}@example.com',
        password='Str0ng-pass-123', gender=User.Gender.FEMALE, role=role,
    )


def scores(**extra):
    data = {'date': str(timezone.localdate()), 'sleep': 4, 'wellbeing': 3,
            'stress': 2, 'hunger': 3}
    data.update(extra)
    return data


class CheckinTests(APITestCase):

    def setUp(self):
        self.anna = make_user('anna')
        self.olga = make_user('olga')
        self.coach = make_user('fox', User.Roles.COACH)
        self.other_coach = make_user('wolf', User.Roles.COACH)
        self.admin = make_user('boss', User.Roles.ADMIN)
        Project.objects.create(
            user=self.anna, coach=self.coach, start_date=timezone.localdate(),
            start_weight=84, target_weight=75, target_calories=2000,
            target_carbohydrate=200, target_fat=70, target_fiber=25,
            target_protein=140, target_sugar=50,
        )

    def test_create_then_replace_the_same_day(self):
        self.client.force_authenticate(self.anna)

        first = self.client.post(URL, scores(weight=82.44), format='json')
        second = self.client.post(URL, scores(sleep=5, weight=None),
                                  format='json')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()['weight'], 82.4)
        self.assertEqual(first.json()['user'], 'anna')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(DailyCheckin.objects.count(), 1)
        checkin = DailyCheckin.objects.get()
        self.assertEqual(checkin.sleep, 5)
        self.assertIsNone(checkin.weight)

    def test_validation(self):
        self.client.force_authenticate(self.anna)
        today = timezone.localdate()
        bad = [
            scores(sleep=0), scores(hunger=6), scores(weight=29),
            scores(weight=301),
            scores(date=str(today + timedelta(days=2))),
            scores(date=str(today - timedelta(days=8))),
        ]
        for payload in bad:
            with self.subTest(payload=payload):
                response = self.client.post(URL, payload, format='json')
                self.assertEqual(response.status_code, 400)
        payload = scores()
        del payload['stress']
        self.assertEqual(
            self.client.post(URL, payload, format='json').status_code, 400,
        )
        self.assertFalse(DailyCheckin.objects.exists())

    def test_only_clients_post(self):
        for user in (self.coach, self.admin):
            self.client.force_authenticate(user)
            response = self.client.post(URL, scores(), format='json')
            self.assertEqual(response.status_code, 403)

    def test_list_is_newest_first_and_last_60_days(self):
        today = timezone.localdate()
        for days_ago in (0, 3, 61):
            DailyCheckin.objects.create(
                user=self.anna, date=today - timedelta(days=days_ago),
                sleep=3, wellbeing=3, stress=3, hunger=3,
            )
        self.client.force_authenticate(self.anna)
        data = self.client.get(URL, {'user': 'anna'}).json()

        self.assertEqual([c['date'] for c in data],
                         [str(today), str(today - timedelta(days=3))])

    def test_who_can_read(self):
        DailyCheckin.objects.create(user=self.anna, date=timezone.localdate(),
                                    sleep=3, wellbeing=3, stress=3, hunger=3)
        cases = [
            (self.anna, 200), (self.coach, 200), (self.admin, 200),
            (self.olga, 403), (self.other_coach, 403),
        ]
        for user, expected in cases:
            with self.subTest(user=user.username):
                self.client.force_authenticate(user)
                response = self.client.get(URL, {'user': 'anna'})
                self.assertEqual(response.status_code, expected)

    def test_needs_a_login(self):
        self.assertEqual(self.client.get(URL).status_code, 401)
