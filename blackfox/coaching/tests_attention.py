from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from checkins.models import DailyCheckin
from coaching.models import CoachClient
from coaching.tests import User, make
from training.models import FoodDiary, Project

TODAY = timezone.localdate()


def day(back):
    return TODAY - timedelta(days=back)


def plan(user, coach, started=40, start=84, target=75):
    return Project.objects.create(
        user=user, coach=coach, start_date=day(started), start_weight=start,
        target_weight=target, target_calories=2000, target_carbohydrate=200,
        target_fat=70, target_fiber=25, target_protein=140, target_sugar=50,
    )


def food(user, back, calories=1900, target=2000, weight=0):
    FoodDiary.objects.create(
        user=user, date=day(back), calories_actual=calories,
        calories_target=target, protein_actual=130, protein_target=140,
        fat_actual=60, fat_target=70, carbohydrate_actual=200,
        carbohydrate_target=200, fiber_actual=20, fiber_target=25,
        sugar_actual=30, sugar_target=50, weight_actual=weight,
        weight_target=75,
    )


class AttentionTests(APITestCase):

    def setUp(self):
        self.fox = make('fox', User.Roles.COACH)
        self.wolf = make('wolf', User.Roles.COACH)

    def client_of(self, name, coach=None):
        user = make(name)
        user.fatsecret_token, user.fatsecret_secret = 't', 's'
        user.save()
        return user

    def kinds(self):
        self.client.force_authenticate(self.fox)
        rows = self.client.get('/api/coach/attention/').json()
        return {r['username']: [x['kind'] for x in r['reasons']]
                for r in rows}

    def test_quiet_client_is_not_listed(self):
        anna = self.client_of('anna')
        plan(anna, self.fox)
        for back in range(0, 21):
            food(anna, back, weight=84 - (21 - back) * 0.1)
        self.assertEqual(self.kinds(), {})

    def test_no_food_and_over_the_target(self):
        olga = self.client_of('olga')
        plan(olga, self.fox)
        food(olga, 5)  # nothing for the last 3 days
        ivan = self.client_of('ivan')
        plan(ivan, self.fox)
        for back in (1, 2, 3):
            food(ivan, back, calories=2500)
        kinds = self.kinds()
        self.assertIn('no_food', kinds['olga'])
        self.assertIn('over', kinds['ivan'])

    def test_weight_stalled_for_two_weeks(self):
        max_ = self.client_of('max')
        plan(max_, self.fox)
        for back in range(0, 21):
            food(max_, back, weight=82.0)
        self.assertIn('stall', self.kinds()['max'])

    def test_bad_checkins_and_waiting_for_a_plan(self):
        lena = self.client_of('lena')
        plan(lena, self.fox, started=3)
        for back in (0, 1, 2):
            DailyCheckin.objects.create(user=lena, date=day(back), sleep=1,
                                        wellbeing=2, stress=5, hunger=2)
        kate = self.client_of('kate')
        link = CoachClient.objects.create(client=kate, coach=self.fox)
        CoachClient.objects.filter(pk=link.pk).update(
            joined_at=timezone.now() - timedelta(days=2))
        kinds = self.kinds()
        self.assertIn('sleep', kinds['lena'])
        self.assertIn('stress', kinds['lena'])
        self.assertNotIn('hunger', kinds['lena'])
        self.assertEqual(kinds['kate'], ['waiting'])

    def test_only_own_clients_and_urgent_first(self):
        stranger = self.client_of('stranger')
        plan(stranger, self.wolf)
        food(stranger, 9)
        olga = self.client_of('olga')
        plan(olga, self.fox)
        food(olga, 5)
        self.client.force_authenticate(self.fox)
        rows = self.client.get('/api/coach/attention/').json()
        self.assertEqual([r['username'] for r in rows], ['olga'])
        self.assertEqual(rows[0]['reasons'][0]['severity'], 2)
        self.client.force_authenticate(olga)
        self.assertEqual(self.client.get('/api/coach/attention/')
                         .status_code, 403)
