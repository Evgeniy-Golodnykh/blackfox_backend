from datetime import date, timedelta

from django.utils import timezone
from rest_framework.test import APITestCase

from checkins.models import DailyCheckin
from coaching.models import CoachClient, DayComment
from coaching.tests import User, make, project_for
from course.models import Enrollment, Lesson, LessonRead
from training.models import FoodDiary

TODAY = date.today()


def food(user, back):
    FoodDiary.objects.create(
        user=user, date=TODAY - timedelta(days=back), calories_actual=1900,
        calories_target=2000, protein_actual=130, protein_target=140,
        fat_actual=60, fat_target=70, carbohydrate_actual=200,
        carbohydrate_target=200, fiber_actual=20, fiber_target=25,
        sugar_actual=30, sugar_target=50, weight_actual=0, weight_target=75)


def joined(user, days_ago):
    User.objects.filter(pk=user.pk).update(
        date_joined=timezone.now() - timedelta(days=days_ago))
    user.refresh_from_db()


class AnalyticsTests(APITestCase):

    def setUp(self):
        self.boss = make('boss', User.Roles.ADMIN)
        self.fox = make('fox', User.Roles.COACH)
        self.anna = make('anna')   # plan, logs daily
        self.olga = make('olga')   # joined fox, waiting
        self.ivan = make('ivan')   # nothing
        project_for(self.anna, self.fox)
        CoachClient.objects.create(client=self.olga, coach=self.fox)
        for back in range(7):
            food(self.anna, back)
        self.client.force_authenticate(self.boss)

    def get(self, days=30):
        response = self.client.get('/api/admin/analytics/', {'days': days})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_clients_and_engagement(self):
        data = self.get()
        self.assertEqual(data['clients'],
                         {'total': 3, 'active': 1, 'waiting': 1, 'new': 3})
        self.assertEqual(data['engagement']['food_days_per_week'], 7.0)
        self.assertEqual(data['engagement']['active_week_percent'], 100)
        self.assertIsNone(data['payments'])

    def test_retention_on_day_7(self):
        joined(self.anna, 20)   # active days 7–13 after sign-up
        joined(self.ivan, 20)   # gone
        DailyCheckin.objects.create(user=self.anna, date=TODAY - timedelta(10),
                                    sleep=3, wellbeing=3, stress=3, hunger=3)
        food(self.anna, 12)
        r7 = self.get()['engagement']['retention_7']
        self.assertEqual(r7['cohort'], 2)
        self.assertEqual(r7['percent'], 50)

    def test_course_and_coaches(self):
        Enrollment.objects.create(user=self.anna, started_on=TODAY)
        for lesson in Lesson.objects.all():
            LessonRead.objects.create(user=self.anna, lesson=lesson)
        Enrollment.objects.create(user=self.olga, started_on=TODAY)
        DayComment.objects.create(client=self.anna, coach=self.fox,
                                  date=TODAY, text='ок')
        data = self.get()
        self.assertEqual((data['course']['enrolled'],
                          data['course']['finished']), (2, 1))
        coach = data['coaches'][0]
        self.assertEqual((coach['username'], coach['clients'],
                          coach['waiting'], coach['comments_week']),
                         ('fox', 2, 1, 1))

    def test_only_admin(self):
        self.client.force_authenticate(self.fox)
        self.assertEqual(self.client.get('/api/admin/analytics/')
                         .status_code, 403)
