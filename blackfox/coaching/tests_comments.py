from datetime import timedelta
from unittest import mock

from django.utils import timezone
from rest_framework.test import APITestCase

from coaching.comments import purge_old
from coaching.models import CoachClient, DayComment
from coaching.tests import User, make, project_for
from tgbot.digest import daily_report
from tgbot.models import NotificationLog, NotificationSettings
from training.models import FoodDiary

TODAY = timezone.localdate()


def day(back):
    return TODAY - timedelta(days=back)


@mock.patch('tgbot.onboarding.send_later')
class DayCommentTests(APITestCase):

    def setUp(self):
        self.fox = make('fox', User.Roles.COACH)
        self.wolf = make('wolf', User.Roles.COACH)
        self.anna = make('anna')
        project_for(self.anna, self.fox)

    def put(self, user, date, text, who='anna'):
        self.client.force_authenticate(user)
        return self.client.put(f'/api/day-comments/{who}/{date}/',
                               {'text': text}, format='json')

    def test_coach_writes_edits_and_clears(self, _):
        response = self.put(self.fox, day(0), 'Отличный день!')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['coach'], 'Fox')
        self.put(self.fox, day(0), 'Отличный день, белок в норме')
        self.assertEqual(DayComment.objects.get().text,
                         'Отличный день, белок в норме')
        self.assertEqual(self.put(self.fox, day(0), '').status_code, 204)
        self.assertFalse(DayComment.objects.exists())

    def test_client_reads_own_only(self, _):
        self.put(self.fox, day(1), 'Хорошо')
        self.client.force_authenticate(self.anna)
        rows = self.client.get('/api/day-comments/').json()
        self.assertEqual([r['text'] for r in rows], ['Хорошо'])
        olga = make('olga')
        self.client.force_authenticate(olga)
        # A client can't read someone else's by ?user=.
        self.assertEqual(
            self.client.get('/api/day-comments/', {'user': 'anna'}).json(),
            [])

    def test_only_own_coach_and_only_two_weeks(self, _):
        self.assertEqual(self.put(self.wolf, day(0), 'x').status_code, 403)
        self.assertEqual(self.put(self.anna, day(0), 'x').status_code, 403)
        self.assertEqual(self.put(self.fox, day(14), 'x').status_code, 400)
        self.assertEqual(self.put(self.fox, day(-1), 'x').status_code, 400)
        self.assertEqual(self.put(self.fox, 'nope', 'x').status_code, 400)

    def test_old_comments_are_deleted(self, _):
        DayComment.objects.create(client=self.anna, coach=self.fox,
                                  date=day(20), text='старый')
        DayComment.objects.create(client=self.anna, coach=self.fox,
                                  date=day(3), text='свежий')
        self.assertEqual(purge_old(), 1)
        kept = DayComment.objects.values_list('text', flat=True)
        self.assertEqual(list(kept), ['свежий'])

    def test_today_rides_in_the_report_else_sent_now(self, send_later):
        NotificationSettings.objects.create(user=self.anna,
                                            daily_report=True)
        self.put(self.fox, day(0), 'Сегодня — в отчёте')
        send_later.assert_not_called()
        self.put(self.fox, day(1), 'Вчерашний — сразу')
        send_later.assert_called_once()
        # Today's report already went: sent on its own.
        NotificationLog.objects.create(user=self.anna, kind='daily_report',
                                       date=day(0))
        DayComment.objects.filter(date=day(0)).delete()
        self.put(self.fox, day(0), 'После отчёта')
        self.assertEqual(send_later.call_count, 2)

    def test_report_carries_the_comment(self, _):
        FoodDiary.objects.create(
            user=self.anna, date=day(0), calories_actual=1800,
            calories_target=2000, protein_actual=120, protein_target=140,
            fat_actual=60, fat_target=70, carbohydrate_actual=200,
            carbohydrate_target=210, fiber_actual=20, fiber_target=25,
            sugar_actual=30, sugar_target=50, weight_actual=0,
            weight_target=75)
        DayComment.objects.create(client=self.anna, coach=self.fox,
                                  date=day(0), text='Молодец!')
        message = daily_report(self.anna, day(0))
        self.assertIn('💬 Тренер: Молодец!', message.text)

    def test_coach_of_a_joined_client_too(self, _):
        olga = make('olga')
        CoachClient.objects.create(client=olga, coach=self.fox)
        self.assertEqual(self.put(self.fox, day(0), 'Привет', 'olga')
                         .status_code, 200)
