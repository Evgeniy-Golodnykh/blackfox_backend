from rest_framework.test import APITestCase

from coaching.models import CoachClient
from coaching.tests import User, make, project_for
from users.models import CoachProfile

URL = '/api/admin/users/{}/'


class AdminUserTests(APITestCase):

    def setUp(self):
        self.boss = make('boss', User.Roles.ADMIN)
        self.fox = make('fox', User.Roles.COACH)
        self.wolf = make('wolf', User.Roles.COACH)
        self.anna = make('anna')
        self.client.force_authenticate(self.boss)

    def patch(self, username, data):
        return self.client.patch(URL.format(username), data, format='json')

    def test_admin_edits_main_data_without_deactivating(self):
        response = self.patch('anna', {'first_name': 'анна', 'email':
                                       'New@Example.com', 'gender': 'female'})
        self.assertEqual(response.status_code, 200, response.content)
        self.anna.refresh_from_db()
        self.assertEqual(self.anna.first_name, 'Анна')
        self.assertEqual(self.anna.email, 'new@example.com')
        self.assertTrue(self.anna.is_active)  # unlike a self-service change

    def test_block_and_unblock(self):
        self.patch('anna', {'is_active': False})
        self.anna.refresh_from_db()
        self.assertFalse(self.anna.is_active)
        self.patch('anna', {'is_active': True})
        self.anna.refresh_from_db()
        self.assertTrue(self.anna.is_active)

    def test_coach_profile(self):
        response = self.patch('fox', {'coach_profile': {
            'specialization': ['Снижение веса'], 'experience_years': 5,
            'bio': 'Тренер', 'price': '10 000 ₽'}})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(CoachProfile.objects.get(user=self.fox)
                         .experience_years, 5)
        self.assertEqual(response.json()['coach_profile']['bio'], 'Тренер')

    def test_role_guards(self):
        self.assertEqual(self.patch('boss', {'role': 'user'}).status_code,
                         400)  # not their own
        CoachClient.objects.create(client=self.anna, coach=self.fox)
        self.assertEqual(self.patch('fox', {'role': 'user'}).status_code,
                         400)  # has clients
        self.assertEqual(self.patch('anna', {'role': 'coach'}).status_code,
                         400)  # has a coach
        self.assertEqual(self.patch('wolf', {'role': 'user'}).status_code,
                         200)
        self.assertEqual(self.patch('anna', {'role': 'admin'}).status_code,
                         400)

    def test_duplicate_email_and_only_admin(self):
        self.assertEqual(self.patch('anna', {'email': 'fox@example.com'})
                         .status_code, 400)
        self.client.force_authenticate(self.fox)
        self.assertEqual(self.client.get(URL.format('anna')).status_code,
                         403)

    def test_read_shows_coach_and_links(self):
        project_for(self.anna, self.fox)
        data = self.client.get(URL.format('anna')).json()
        self.assertEqual(data['coach'], 'fox')
        self.assertFalse(data['fatsecret_account'])


class MoveWithPlanTests(APITestCase):

    def test_admin_moves_client_with_the_plan(self):
        from unittest import mock

        from training.models import Project

        boss = make('boss', User.Roles.ADMIN)
        fox = make('fox', User.Roles.COACH)
        wolf = make('wolf', User.Roles.COACH)
        anna = make('anna')
        project_for(anna, wolf)
        self.client.force_authenticate(boss)
        with mock.patch('coaching.services.notify_coach_of_assigned_client'):
            refused = self.client.post('/api/coach/assign/',
                                       {'client': 'anna', 'coach': 'fox'},
                                       format='json')
            self.assertEqual(refused.status_code, 409)
            moved = self.client.post(
                '/api/coach/assign/',
                {'client': 'anna', 'coach': 'fox', 'with_plan': True},
                format='json')
        self.assertEqual(moved.status_code, 200, moved.content)
        self.assertEqual(Project.objects.get(user=anna).coach, fox)
        self.assertEqual(CoachClient.objects.get(client=anna).coach, fox)


class AdminDoesWhatTheCoachDoesTests(APITestCase):
    """On any client's plan the admin can do everything their coach can."""

    def setUp(self):
        from datetime import date, timedelta

        self.boss = make('boss', User.Roles.ADMIN)
        self.fox = make('fox', User.Roles.COACH)
        self.anna = make('anna')
        self.olga = make('olga')
        self.yesterday = str(date.today() - timedelta(days=1))
        self.client.force_authenticate(self.boss)

    def test_plan_create_and_edit(self):
        from datetime import date

        created = self.client.post('/api/project/', {
            'user': 'olga', 'coach': 'fox', 'start_date': str(date.today()),
            'start_weight': 84, 'target_weight': 75, 'target_calories': 2000,
            'target_carbohydrate': 200, 'target_fat': 70, 'target_fiber': 25,
            'target_protein': 140, 'target_sugar': 50}, format='json')
        self.assertEqual(created.status_code, 201, created.content)
        edited = self.client.patch(f"/api/project/{created.json()['id']}/",
                                   {'target_calories': 1800}, format='json')
        self.assertEqual(edited.status_code, 200, edited.content)

    def test_measurements_comments_and_reads(self):
        project_for(self.anna, self.fox)
        body = self.client.post('/api/bodystats/?user=anna',
                                {'date': self.yesterday, 'waist': 80},
                                format='json')
        self.assertIn(body.status_code, (200, 201), body.content)
        from unittest import mock
        with mock.patch('tgbot.onboarding.send_later'):
            comment = self.client.put(
                f'/api/day-comments/anna/{self.yesterday}/',
                {'text': 'Хорошо'}, format='json')
        self.assertEqual(comment.status_code, 200, comment.content)
        for url in ('/api/fooddiary/?user=anna', '/api/bodystats/?user=anna',
                    '/api/checkins/?user=anna', '/api/project/?user=anna'):
            self.assertEqual(self.client.get(url).status_code, 200, url)
