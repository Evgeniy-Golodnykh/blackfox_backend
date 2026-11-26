from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from coaching.models import CoachClient
from course.bot import lesson_message
from course.lessons_first14 import LESSONS
from course.models import Enrollment, Lesson, LessonRead

User = get_user_model()


def make(name, role=User.Roles.USER, joined_days_ago=0):
    user = User.objects.create_user(
        username=name, email=f'{name}@example.com', password='Str0ng-pass-1',
        gender=User.Gender.FEMALE, role=role,
    )
    if joined_days_ago:
        User.objects.filter(pk=user.pk).update(
            date_joined=timezone.now() - timedelta(days=joined_days_ago))
        user.refresh_from_db()
    return user


class LessonsLoadedTests(APITestCase):

    def test_fourteen_lessons_with_sources(self):
        # The data migration loads them (test DB runs migrations).
        self.assertEqual(Lesson.objects.count(), 14)
        self.assertEqual(len(LESSONS), 14)
        for lesson in Lesson.objects.all():
            self.assertTrue(lesson.title and lesson.body and lesson.action)
            self.assertTrue(lesson.sources, lesson.day)
            self.assertLessEqual(len(lesson.summary), 200)


class CourseApiTests(APITestCase):

    def setUp(self):
        self.anna = make('anna')  # just signed up

    def get(self, user, url='/api/course/'):
        self.client.force_authenticate(user)
        return self.client.get(url)

    def test_new_client_is_enrolled_on_first_visit(self):
        data = self.get(self.anna).json()
        self.assertTrue(data['enrolled'])
        self.assertEqual(data['day'], 1)
        self.assertEqual(data['total'], 14)
        self.assertTrue(data['lessons'][0]['unlocked'])
        self.assertFalse(data['lessons'][1]['unlocked'])

    def test_old_client_starts_by_button(self):
        olga = make('olga', joined_days_ago=40)
        self.assertFalse(self.get(olga).json()['enrolled'])
        self.client.force_authenticate(olga)
        started = self.client.post('/api/course/start/').json()
        self.assertTrue(started['enrolled'])

    def test_one_lesson_a_day_and_reading_marks_it(self):
        self.get(self.anna)
        Enrollment.objects.filter(user=self.anna).update(
            started_on=date.today() - timedelta(days=2))
        self.assertEqual(self.get(self.anna, '/api/course/lessons/4/')
                         .status_code, 403)
        lesson = self.get(self.anna, '/api/course/lessons/3/').json()
        self.assertEqual(lesson['day'], 3)
        self.assertTrue(lesson['sources'])
        overview = self.get(self.anna).json()
        self.assertEqual(overview['day'], 3)
        self.assertEqual(overview['read'], 1)
        self.assertTrue(overview['lessons'][2]['read'])

    def test_coach_sees_progress_of_own_client(self):
        fox = make('fox', User.Roles.COACH)
        CoachClient.objects.create(client=self.anna, coach=fox)
        self.get(self.anna, '/api/course/')
        self.get(self.anna, '/api/course/lessons/1/')
        rows = self.get(fox, '/api/coach/clients/').json()
        self.assertEqual(rows[0]['course'], {'read': 1, 'total': 14})

    def test_coaches_are_not_enrolled(self):
        fox = make('fox', User.Roles.COACH)
        self.assertFalse(self.get(fox).json()['enrolled'])
        self.client.force_authenticate(fox)
        self.assertEqual(self.client.post('/api/course/start/').status_code,
                         403)

    def test_bot_lessons_can_be_turned_off(self):
        self.get(self.anna)
        self.client.force_authenticate(self.anna)
        data = self.client.patch('/api/course/', {'bot_lessons': False},
                                 format='json').json()
        self.assertFalse(data['bot_lessons'])


class BotLessonTests(APITestCase):

    def setUp(self):
        self.anna = make('anna')
        Enrollment.objects.create(user=self.anna,
                                  started_on=date.today() - timedelta(days=5))

    def test_todays_lesson_until_read(self):
        message = lesson_message(self.anna, date.today())
        self.assertIn('день 6 из 14', message.text)
        self.assertEqual(message.button, ('Читать урок', '/learn/6'))
        LessonRead.objects.create(user=self.anna,
                                  lesson=Lesson.objects.get(day=6))
        self.assertIsNone(lesson_message(self.anna, date.today()))

    def test_nothing_after_the_course_or_when_off(self):
        self.assertIsNone(lesson_message(self.anna,
                                         date.today() + timedelta(days=30)))
        Enrollment.objects.filter(user=self.anna).update(bot_lessons=False)
        self.assertIsNone(lesson_message(self.anna, date.today()))

    @mock.patch('tgbot.scheduler.refresh_diary')
    def test_scheduler_sends_it_in_the_morning(self, _):
        from tgbot.models import NotificationSettings
        from tgbot.scheduler import due_messages

        prefs = NotificationSettings(user=self.anna, daily_report=False,
                                     weekly_report=False,
                                     checkin_reminder=False, reminders=False)
        morning = timezone.now().replace(hour=6, minute=10)  # 09:10 МСК
        kinds = [m.kind for m, _ in due_messages(self.anna, prefs, morning,
                                                 refresh=False)]
        self.assertIn('lesson', kinds)
