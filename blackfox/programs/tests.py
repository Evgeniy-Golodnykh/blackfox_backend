from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from programs.models import (
    ProgramDay, ProgramEnrollment, TrainingProgram, WorkoutLog,
)

User = get_user_model()
START = date(2026, 11, 2)


def make(name):
    return User.objects.create_user(
        username=name, email=f'{name}@example.com', password='Str0ng-pass-1',
        gender=User.Gender.FEMALE, role=User.Roles.USER)


def on(day):
    """Patch «today» to the given day of the program (1 — the start)."""

    return mock.patch('programs.views.local_today',
                      return_value=START + timedelta(days=day - 1))


class ProgramsLoadedTests(APITestCase):

    def test_four_closed_programs(self):
        self.assertEqual(
            set(TrainingProgram.objects.values_list('slug', flat=True)),
            {'hyrox', 'crossfit', 'running', 'functional'})
        self.assertFalse(TrainingProgram.objects.filter(
            is_published=True).exists())


class ProgramApiTests(APITestCase):

    def setUp(self):
        self.program = TrainingProgram.objects.get(slug='hyrox')
        # Training on days 1, 3, 8 and 10; the rest are rest days.
        for day in (1, 3, 8, 10):
            ProgramDay.objects.create(
                program=self.program, day=day, title=f'День {day}',
                base=f'База {day}', hard=f'Сложно {day}' if day == 1 else '')
        self.anna = make('anna')
        self.client.force_authenticate(self.anna)

    def start(self):
        with on(1):
            return self.client.post('/api/programs/hyrox/start/')

    def test_a_closed_program_cant_be_started(self):
        response = self.start()
        self.assertEqual(response.status_code, 404)
        info = self.client.get('/api/programs/hyrox/')
        self.assertEqual(info.status_code, 404)
        self.assertFalse(info.json()['available'])

    def test_days_open_one_by_one_and_the_free_week(self):
        self.program.is_published = True
        self.program.save()
        data = self.start().json()
        self.assertEqual(data['current_day'], 1)
        self.assertEqual(data['today']['day'], 1)
        self.assertEqual([d['state'] for d in data['days']],
                         ['open', 'later', 'later', 'later'])

        with on(1):
            day = self.client.get('/api/programs/hyrox/days/1/').json()
            self.assertEqual(day['versions'], {
                'easy': 'База 1', 'base': 'База 1', 'hard': 'Сложно 1'})
            self.assertEqual(day['next_day'], 3)
            self.assertEqual(
                self.client.get('/api/programs/hyrox/days/3/').status_code,
                403)

        with on(2):
            data = self.client.get('/api/programs/hyrox/').json()
            self.assertIsNone(data['today'])  # a rest day
            self.assertEqual(data['next_day'], 3)

        # Day 8 has come, but the free week is over.
        with on(8):
            data = self.client.get('/api/programs/hyrox/').json()
            self.assertEqual(data['today']['state'], 'paywall')
            response = self.client.get('/api/programs/hyrox/days/8/')
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['state'], 'paywall')
            # Paid days open; the free week stays open.
            ProgramEnrollment.objects.update(
                paid_until=START + timedelta(days=36))
            self.assertEqual(
                self.client.get('/api/programs/hyrox/days/8/').status_code,
                200)
            self.assertEqual(
                self.client.get('/api/programs/hyrox/days/10/').status_code,
                403)  # not yet

    def test_the_diary(self):
        self.program.is_published = True
        self.program.save()
        self.start()
        with on(1):
            response = self.client.put(
                '/api/programs/hyrox/days/1/',
                {'level': 'hard', 'result': '25:40', 'feel': 4},
                format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['log']['result'], '25:40')
            bad = self.client.put('/api/programs/hyrox/days/1/',
                                  {'feel': 9}, format='json')
            self.assertEqual(bad.status_code, 400)
        with on(3):
            # Editing later keeps the day it was done.
            self.client.put('/api/programs/hyrox/days/1/',
                            {'note': 'Тяжело'}, format='json')
            log = WorkoutLog.objects.get()
            self.assertEqual((log.done_on, log.result, log.note),
                             (START, '25:40', 'Тяжело'))
            data = self.client.get('/api/programs/hyrox/').json()
            self.assertEqual(data['days'][0]['done'], True)
            self.assertEqual(data['days'][0]['level'], 'hard')
            self.assertEqual(data['done_count'], 1)
            diary = self.client.get('/api/programs/hyrox/diary/').json()
            self.assertEqual([(e['day'], e['level']) for e in diary],
                             [(1, 'hard')])
            # A future day can't be logged.
            self.assertEqual(self.client.put(
                '/api/programs/hyrox/days/8/', {'result': 'x'},
                format='json').status_code, 403)
            self.client.delete('/api/programs/hyrox/days/1/')
            self.assertFalse(WorkoutLog.objects.exists())

    def test_someone_elses_progress_is_not_shown(self):
        self.program.is_published = True
        self.program.save()
        self.start()
        self.client.force_authenticate(make('olga'))
        self.assertEqual(self.client.get('/api/programs/').json(), [])
        with on(1):
            self.assertEqual(self.client.get(
                '/api/programs/hyrox/days/1/').status_code, 404)

    def test_starting_again_keeps_the_progress(self):
        self.program.is_published = True
        self.program.save()
        self.start()
        with on(5):
            data = self.client.post('/api/programs/hyrox/start/').json()
        self.assertEqual(data['started_on'], START.isoformat())
        self.assertEqual(data['current_day'], 5)


class WorkoutReminderTests(APITestCase):

    def setUp(self):
        self.program = TrainingProgram.objects.get(slug='hyrox')
        self.program.is_published = True
        self.program.save()
        for day in (1, 3, 8):
            ProgramDay.objects.create(program=self.program, day=day,
                                      title=f'День {day}', base='x')
        self.anna = make('anna')
        ProgramEnrollment.objects.create(user=self.anna,
                                         program=self.program,
                                         started_on=START)

    def message(self, day):
        from programs.bot import workout_message
        return workout_message(self.anna, START + timedelta(days=day - 1))

    def test_today_open_and_not_done(self):
        message = self.message(1)
        self.assertEqual(message.kind, 'workout')
        self.assertIn('Hyrox · день 1', message.text)
        self.assertEqual(message.button,
                         ('Открыть тренировку',
                          '/more/online-programs/hyrox/hyrox/days/1'))

    def test_quiet_on_rest_days_done_days_and_behind_the_paywall(self):
        self.assertIsNone(self.message(2))  # rest
        WorkoutLog.objects.create(user=self.anna, day=ProgramDay.objects.get(
            program=self.program, day=3), done_on=START)
        self.assertIsNone(self.message(3))  # already done
        self.assertIsNone(self.message(8))  # the free week is over
        ProgramEnrollment.objects.update(
            paid_until=START + timedelta(days=30))
        self.assertIsNotNone(self.message(8))

    def test_a_closed_program_is_quiet(self):
        self.program.is_published = False
        self.program.save()
        self.assertIsNone(self.message(1))


class AdminProgramsApiTests(APITestCase):

    def setUp(self):
        self.boss = make('boss')
        self.boss.role = User.Roles.ADMIN
        self.boss.save()
        self.client.force_authenticate(self.boss)

    def test_write_days_and_open_the_program(self):
        url = '/api/admin/programs/hyrox/'
        created = self.client.post(url + 'days/', {
            'day': 1, 'title': 'Бег и станции', 'base': '## Разминка'},
            format='json')
        self.assertEqual(created.status_code, 201)
        twice = self.client.post(url + 'days/', {
            'day': 1, 'title': 'x', 'base': 'x'}, format='json')
        self.assertEqual(twice.status_code, 400)
        self.client.put(url + 'days/1/', {'easy': 'Легче', 'day': 2},
                        format='json')
        row = ProgramDay.objects.get()
        self.assertEqual((row.day, row.easy), (2, 'Легче'))
        data = self.client.patch(url, {'is_published': True},
                                 format='json').json()
        self.assertTrue(data['is_published'])
        self.assertEqual(data['days'], [{'day': 2, 'title': 'Бег и станции'}])
        listed = self.client.get('/api/admin/programs/').json()
        self.assertEqual(len(listed), 4)
        self.assertEqual(self.client.delete(url + 'days/2/').status_code, 204)

    def test_clients_cant(self):
        self.client.force_authenticate(make('anna'))
        self.assertEqual(
            self.client.get('/api/admin/programs/').status_code, 403)
        self.assertEqual(self.client.post(
            '/api/admin/programs/hyrox/days/',
            {'day': 1, 'title': 'x', 'base': 'x'}, format='json',
        ).status_code, 403)


class ImportAndPriceTests(APITestCase):

    def setUp(self):
        boss = make('boss')
        boss.role = User.Roles.ADMIN
        boss.save()
        self.client.force_authenticate(boss)
        self.url = '/api/admin/programs/hyrox/'
        self.program = TrainingProgram.objects.get(slug='hyrox')

    def days(self, *numbers):
        return [{'day': n, 'title': f'Тема {n}', 'base': f'База {n}',
                 'easy': '', 'hard': f'Сложно {n}'} for n in numbers]

    def test_upload_adds_and_rewrites(self):
        ProgramDay.objects.create(program=self.program, day=1,
                                  title='Старое', base='старое')
        data = self.client.post(self.url + 'import/',
                                {'days': self.days(1, 3, 5)},
                                format='json').json()
        self.assertEqual((data['created'], data['updated'], data['deleted']),
                         (2, 1, 0))
        self.assertEqual(ProgramDay.objects.get(day=1).title, 'Тема 1')
        self.assertEqual(ProgramDay.objects.get(day=5).hard, 'Сложно 5')

    def test_replace_drops_the_rest_and_bad_uploads_change_nothing(self):
        self.client.post(self.url + 'import/', {'days': self.days(1, 2, 3)},
                         format='json')
        data = self.client.post(self.url + 'import/',
                                {'days': self.days(2), 'replace': True},
                                format='json').json()
        self.assertEqual(data['deleted'], 2)
        self.assertEqual(
            list(ProgramDay.objects.values_list('day', flat=True)), [2])
        twice = self.client.post(self.url + 'import/',
                                 {'days': self.days(4, 4), 'replace': True},
                                 format='json')
        self.assertEqual(twice.status_code, 400)
        empty_base = self.days(6)
        empty_base[0]['base'] = ''
        self.assertEqual(self.client.post(
            self.url + 'import/', {'days': empty_base},
            format='json').status_code, 400)
        self.assertEqual(
            list(ProgramDay.objects.values_list('day', flat=True)), [2])

    def test_price_set_in_the_app_and_shown_in_the_shop(self):
        self.assertIsNone(self.client.get(self.url).json()['price'])
        self.assertEqual(self.client.patch(self.url, {'price': 'abc'},
                                           format='json').status_code, 400)
        self.assertEqual(self.client.patch(
            self.url, {'price': 2490}, format='json').json()['price'], 2490)
        self.client.force_authenticate(make('anna'))
        catalog = {row['program']: row for row in
                   self.client.get('/api/programs/catalog/').json()}
        self.assertEqual(catalog['hyrox']['price'], 2490)
        self.assertIsNone(catalog['running']['price'])
        self.assertEqual(self.client.post(
            self.url + 'import/', {'days': self.days(1)},
            format='json').status_code, 403)
