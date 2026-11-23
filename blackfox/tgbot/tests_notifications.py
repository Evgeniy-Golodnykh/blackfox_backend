from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from activity.models import ActivityDay
from checkins.models import DailyCheckin
from tgbot import cards, digest, scheduler
from tgbot.models import NotificationLog, NotificationSettings, TelegramAccount
from tgbot.telegram_api import BLOCKED, FAILED, SENT
from training.models import BodyStatsDiary, FoodDiary, Project

User = get_user_model()

TODAY = date(2026, 11, 23)  # a Monday
TG_ID = 555000111


def make_client(name='anna', fatsecret=True):
    user = User.objects.create_user(
        username=name, email=f'{name}@example.com', password='Str0ng-pass-1',
        gender=User.Gender.FEMALE, role=User.Roles.USER,
        fatsecret_token='t' if fatsecret else None,
        fatsecret_secret='s' if fatsecret else None,
    )
    coach = User.objects.create_user(
        username=f'{name}-coach', email=f'{name}-coach@example.com',
        password='Str0ng-pass-1', gender=User.Gender.MALE,
        role=User.Roles.COACH,
    )
    Project.objects.create(
        user=user, coach=coach, start_date=TODAY - timedelta(days=60),
        start_weight=84, target_weight=75, target_calories=2000,
        target_carbohydrate=210, target_fat=70, target_fiber=25,
        target_protein=140, target_sugar=50,
    )
    return user


def eat(user, day, calories=1900, protein=145, weight=0):
    return FoodDiary.objects.create(
        user=user, date=day, calories_actual=calories, calories_target=2000,
        protein_actual=protein, protein_target=140, fat_actual=64,
        fat_target=70, carbohydrate_actual=190, carbohydrate_target=210,
        fiber_actual=18, fiber_target=25, sugar_actual=30, sugar_target=50,
        weight_actual=weight, weight_target=75,
    )


def moscow(day, hh_mm):
    return scheduler.as_local(f'{day.isoformat()} {hh_mm}')


class DigestTests(TestCase):

    def setUp(self):
        self.user = make_client()

    def test_daily_report_text(self):
        for back in (1, 2):
            eat(self.user, TODAY - timedelta(days=back))
        eat(self.user, TODAY, calories=1840, protein=150)

        message = digest.daily_report(self.user, TODAY)

        self.assertEqual(message.kind, 'daily_report')
        self.assertTrue(message.text.startswith('📊 Отчёт за 23 ноября'))
        self.assertIn('1 840 / 2 000 ккал · 92%', message.text)
        self.assertIn('Белки 150 / 140 г', message.text)
        self.assertIn('✅ В пределах нормы', message.text)
        self.assertIn('🔥 3 дня подряд в норме', message.text)
        self.assertNotIn('Белка не хватило', message.text)
        self.assertEqual(message.button,
                         ('Открыть день', '/stats?day=2026-11-23'))

    def test_daily_report_flags_low_protein(self):
        eat(self.user, TODAY, calories=1840, protein=118)
        text = digest.daily_report(self.user, TODAY).text
        self.assertIn('✅ В пределах нормы', text)
        self.assertIn('🥩 Белка не хватило 22 г', text)

    def test_daily_report_shows_burned_and_balance(self):
        eat(self.user, TODAY, calories=1840)
        before = digest.daily_report(self.user, TODAY).text
        self.assertNotIn('Потрачено', before)
        ActivityDay.objects.create(user=self.user, date=TODAY,
                                   calories_burned=2335)
        self.assertIn('⚡️ Потрачено 2\u00a0335 ккал · баланс ≈ −495 (оценка)',
                      digest.daily_report(self.user, TODAY).text)
        with mock.patch('tgbot.cards.meals_for', return_value=[]):
            self.assertEqual(cards.day_card(self.user, TODAY)['burned'], 2335)

    def test_daily_report_over_and_under(self):
        eat(self.user, TODAY, calories=2400)
        self.assertIn('⬆️ Больше нормы на 400 ккал',
                      digest.daily_report(self.user, TODAY).text)
        FoodDiary.objects.filter(date=TODAY).update(calories_actual=1500)
        self.assertIn('⬇️ Меньше нормы на 500 ккал',
                      digest.daily_report(self.user, TODAY).text)

    def test_no_report_without_food(self):
        self.assertIsNone(digest.daily_report(self.user, TODAY))

    def test_streak_breaks_on_a_gap_or_an_off_day(self):
        eat(self.user, TODAY)
        eat(self.user, TODAY - timedelta(days=1))
        eat(self.user, TODAY - timedelta(days=3))  # day 2 missing
        self.assertEqual(digest.norm_streak(self.user, TODAY), 2)
        eat(self.user, TODAY - timedelta(days=2), protein=100)  # off target
        self.assertEqual(digest.norm_streak(self.user, TODAY), 2)

    def test_weekly_report(self):
        last_monday = TODAY - timedelta(days=7)
        for offset, calories in enumerate((2000, 1950, 2300, 0, 2050, 1500)):
            if calories:
                eat(self.user, last_monday + timedelta(days=offset),
                    calories=calories)
        FoodDiary.objects.filter(date=last_monday).update(weight_actual=82.0)
        DailyCheckin.objects.create(user=self.user,
                                    date=last_monday + timedelta(days=2),
                                    weight=81.8, sleep=3, wellbeing=3,
                                    stress=3, hunger=3)
        eat(self.user, last_monday - timedelta(days=3), weight=82.5)

        text = digest.weekly_report(self.user, TODAY).text

        self.assertTrue(text.startswith('🗓 Неделя 16–22 ноября'))
        self.assertIn('Записей: 5 из 7 дней', text)
        self.assertIn('Средние калории: 1 960 / 2 000', text)
        self.assertIn('Дней в норме (±10%): 3', text)
        self.assertIn('Вес: 82,5 → 81,9 кг (−0,6)', text)

    def test_no_weekly_report_for_an_empty_week(self):
        self.assertIsNone(digest.weekly_report(self.user, TODAY))

    def test_evening_reminder_priority(self):
        self.assertEqual(digest.evening_reminder(self.user, TODAY).kind,
                         'food')

        for back in (1, 2, 3):
            eat(self.user, TODAY - timedelta(days=back))
        eat(self.user, TODAY, calories=1200, protein=90)
        message = digest.evening_reminder(self.user, TODAY)
        self.assertEqual(message.kind, 'streak')
        self.assertIn('Серия 3 дня', message.text)
        self.assertIn('осталось добрать 50 г белка', message.text)

        FoodDiary.objects.filter(date=TODAY).update(protein_actual=150)
        self.assertEqual(digest.evening_reminder(self.user, TODAY).kind,
                         'weigh_in')

        FoodDiary.objects.filter(date=TODAY).update(weight_actual=81.0)
        self.assertEqual(digest.evening_reminder(self.user, TODAY).kind,
                         'measurements')

        BodyStatsDiary.objects.create(user=self.user,
                                      date=TODAY - timedelta(days=3),
                                      waist=80)
        self.assertIsNone(digest.evening_reminder(self.user, TODAY))

    def test_measurements_every_three_weeks_and_not_every_evening(self):
        eat(self.user, TODAY, weight=81.0)
        BodyStatsDiary.objects.create(user=self.user,
                                      date=TODAY - timedelta(days=20),
                                      waist=80)
        self.assertIsNone(digest.evening_reminder(self.user, TODAY))
        BodyStatsDiary.objects.all().update(date=TODAY - timedelta(days=21))
        self.assertEqual(digest.evening_reminder(self.user, TODAY).kind,
                         'measurements')
        # Sent 3 days ago and still not done: wait a week before asking again.
        recently = {'measurements': TODAY - timedelta(days=3)}
        self.assertIsNone(digest.evening_reminder(self.user, TODAY, recently))
        week = {'measurements': TODAY - timedelta(days=7)}
        self.assertEqual(
            digest.evening_reminder(self.user, TODAY, week).kind,
            'measurements')

    def test_weigh_in_at_least_every_other_day(self):
        BodyStatsDiary.objects.create(user=self.user, date=TODAY, waist=80)
        eat(self.user, TODAY)
        eat(self.user, TODAY - timedelta(days=1), weight=81.4)
        self.assertIsNone(digest.evening_reminder(self.user, TODAY))
        # Last weigh-in two days ago: remind, and again the next evening.
        FoodDiary.objects.filter(user=self.user).update(weight_actual=0)
        eat(self.user, TODAY - timedelta(days=2), weight=81.4)
        self.assertEqual(digest.evening_reminder(self.user, TODAY).kind,
                         'weigh_in')
        sent_yesterday = {'weigh_in': TODAY - timedelta(days=1)}
        self.assertEqual(
            digest.evening_reminder(self.user, TODAY, sent_yesterday).kind,
            'weigh_in')

    def test_checkin_weight_counts(self):
        BodyStatsDiary.objects.create(user=self.user, date=TODAY, waist=80)
        eat(self.user, TODAY)
        DailyCheckin.objects.create(user=self.user, date=TODAY, weight=81.2,
                                    sleep=3, wellbeing=3, stress=3, hunger=3)
        self.assertIsNone(digest.evening_reminder(self.user, TODAY))

    def test_checkin_reminder_only_without_a_checkin(self):
        self.assertEqual(digest.checkin_reminder(self.user, TODAY).kind,
                         'checkin')
        DailyCheckin.objects.create(user=self.user, date=TODAY, sleep=3,
                                    wellbeing=3, stress=3, hunger=3)
        self.assertIsNone(digest.checkin_reminder(self.user, TODAY))


@override_settings(TELEGRAM_REPORT_CARDS=False)
@mock.patch('tgbot.scheduler.time.sleep')
@mock.patch('tgbot.scheduler.refresh_diary')
@mock.patch('tgbot.scheduler.send_message', return_value=SENT)
class SchedulerTests(TestCase):

    def setUp(self):
        self.user = make_client()
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)

    def kinds(self, results):
        return sorted(message.kind for _, message, _ in results)

    def test_morning_checkin_at_its_time_only(self, send, *_):
        self.assertEqual(scheduler.run(now=moscow(TODAY, '07:55')), [])
        results = scheduler.run(now=moscow(TODAY, '08:05'))
        self.assertEqual(self.kinds(results), ['checkin'])
        send.assert_called_once()
        self.assertEqual(send.call_args.args[0], TG_ID)
        # Not again on the next run, and not hours late.
        self.assertEqual(scheduler.run(now=moscow(TODAY, '08:15')), [])
        tomorrow = TODAY + timedelta(days=1)
        self.assertEqual(scheduler.run(now=moscow(tomorrow, '11:30')), [])

    def test_evening(self, send, refresh, _):
        eat(self.user, TODAY)
        DailyCheckin.objects.create(user=self.user, date=TODAY, sleep=3,
                                    wellbeing=3, stress=3, hunger=3)

        at_20 = scheduler.run(now=moscow(TODAY, '20:05'))
        at_21 = scheduler.run(now=moscow(TODAY, '21:05'))

        self.assertEqual(self.kinds(at_20), ['weigh_in'])
        self.assertEqual(self.kinds(at_21), ['daily_report'])
        self.assertTrue(refresh.called)

    def test_monday_summary_at_ten(self, send, *_):
        eat(self.user, TODAY - timedelta(days=3))
        DailyCheckin.objects.create(user=self.user, date=TODAY, sleep=3,
                                    wellbeing=3, stress=3, hunger=3)
        results = scheduler.run(now=moscow(TODAY, '10:05'))
        self.assertEqual(self.kinds(results), ['weekly_report'])

    def test_time_zone(self, send, *_):
        NotificationSettings.objects.create(user=self.user,
                                            timezone='Asia/Omsk')
        # 08:05 in Omsk is 05:05 in Moscow.
        self.assertEqual(self.kinds(scheduler.run(now=moscow(TODAY,
                                                             '05:05'))),
                         ['checkin'])

    def test_switched_off_kinds_are_not_sent(self, send, *_):
        NotificationSettings.objects.create(
            user=self.user, checkin_reminder=False,
        )
        self.assertEqual(scheduler.run(now=moscow(TODAY, '08:05')), [])

    def test_failed_send_is_retried(self, send, *_):
        send.return_value = FAILED
        scheduler.run(now=moscow(TODAY, '08:05'))
        self.assertFalse(NotificationLog.objects.exists())
        send.return_value = SENT
        scheduler.run(now=moscow(TODAY, '08:15'))
        self.assertEqual(NotificationLog.objects.count(), 1)

    def test_blocked_bot_switches_everything_off(self, send, *_):
        send.return_value = BLOCKED
        scheduler.run(now=moscow(TODAY, '08:05'))
        self.assertFalse(TelegramAccount.objects.get().can_write)
        prefs = NotificationSettings.objects.get(user=self.user)
        self.assertFalse(prefs.checkin_reminder or prefs.daily_report)
        send.reset_mock()
        scheduler.run(now=moscow(TODAY + timedelta(days=1), '08:05'))
        send.assert_not_called()

    def test_dry_run_sends_and_logs_nothing(self, send, *_):
        results = scheduler.run(now=moscow(TODAY, '08:05'), dry_run=True)
        self.assertEqual(self.kinds(results), ['checkin'])
        send.assert_not_called()
        self.assertFalse(NotificationLog.objects.exists())

    def test_only_linked_clients(self, send, *_):
        TelegramAccount.objects.all().delete()
        self.assertEqual(scheduler.run(now=moscow(TODAY, '08:05')), [])

    def test_no_food_reminders_without_fatsecret(self, send, *_):
        User.objects.filter(pk=self.user.pk).update(fatsecret_token=None)
        DailyCheckin.objects.create(user=self.user, date=TODAY, sleep=3,
                                    wellbeing=3, stress=3, hunger=3)
        self.assertEqual(scheduler.run(now=moscow(TODAY, '20:05')), [])


TEST_URL = '/api/users/me/telegram/test/'


@override_settings(TELEGRAM_BOT_TOKEN='1:x', TELEGRAM_REPORT_CARDS=False)
@mock.patch('tgbot.scheduler.refresh_diary')
@mock.patch('tgbot.scheduler.send_message', return_value=SENT)
class SendExampleTests(APITestCase):

    def setUp(self):
        self.user = make_client()
        self.client.force_authenticate(self.user)

    def test_needs_a_linked_telegram(self, *_):
        response = self.client.post(TEST_URL, {'kind': 'checkin'},
                                    format='json')
        self.assertEqual(response.status_code, 409)

    def test_sends_the_latest_day(self, send, _):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        self.assertEqual(
            self.client.post(TEST_URL, {'kind': 'daily_report'},
                             format='json').status_code, 404,
        )
        eat(self.user, date.today() - timedelta(days=2))
        response = self.client.post(TEST_URL, {'kind': 'daily_report'},
                                    format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Отчёт за', send.call_args.args[1])
        self.assertFalse(NotificationLog.objects.exists())

    def test_unknown_kind(self, *_):
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        response = self.client.post(TEST_URL, {'kind': 'spam'},
                                    format='json')
        self.assertEqual(response.status_code, 400)


@override_settings(TELEGRAM_BOT_TOKEN='1:x')
@mock.patch('tgbot.telegram_api.time.sleep')
@mock.patch('tgbot.telegram_api.requests.post')
class TelegramApiTests(TestCase):

    def reply(self, status, body=None):
        return mock.Mock(status_code=status, json=lambda: body or {})

    def test_results(self, post, _):
        from tgbot.telegram_api import send_message
        for status, expected in ((200, SENT), (403, BLOCKED), (400, FAILED)):
            post.return_value = self.reply(status)
            self.assertEqual(send_message(1, 'hi', ('Open', '/stats')),
                             expected)
        button = post.call_args.kwargs['json']['reply_markup']
        self.assertEqual(
            button['inline_keyboard'][0][0]['web_app']['url'],
            'https://www.blackfoxnutrition.ru/stats',
        )

    def test_waits_and_retries_once_on_429(self, post, sleep):
        from tgbot.telegram_api import send_message
        post.side_effect = [
            self.reply(429, {'parameters': {'retry_after': 3}}),
            self.reply(200),
        ]
        self.assertEqual(send_message(1, 'hi'), SENT)
        sleep.assert_called_once_with(3)


class CardDataTests(TestCase):

    def setUp(self):
        self.user = make_client()
        self.user.first_name = 'Анна'
        self.user.save()

    def test_day_card(self):
        for back in (1, 2, 4):
            eat(self.user, TODAY - timedelta(days=back), weight=82.0)
        eat(self.user, TODAY, calories=1840, protein=118, weight=81.6)
        with mock.patch('tgbot.cards.meals_for', return_value=[
            {'name': 'Завтрак', 'calories': 420},
        ]):
            data = cards.day_card(self.user, TODAY)

        self.assertEqual(data['kind'], 'day')
        self.assertEqual(data['name'], 'Анна')
        self.assertEqual(data['calories'], 1840)
        self.assertEqual(data['target']['calories'], 2000)
        self.assertEqual(data['streak'], 3)  # day 3 has no food
        self.assertEqual(len(data['last7']), 7)
        self.assertEqual(data['last7'][-1],
                         {'date': '2026-11-23', 'calories': 1840})
        self.assertEqual(data['last7'][3]['calories'], 0)
        self.assertEqual(data['meals'][0]['name'], 'Завтрак')
        self.assertEqual(data['weight']['avg'], 81.9)

    def test_no_card_without_food(self):
        self.assertIsNone(cards.day_card(self.user, TODAY))
        self.assertIsNone(cards.week_card(self.user, TODAY))

    def test_week_card(self):
        eat(self.user, TODAY - timedelta(days=7), calories=2100)
        eat(self.user, TODAY - timedelta(days=2), calories=1800)
        data = cards.week_card(self.user, TODAY)
        self.assertEqual((data['from'], data['to']),
                         ('2026-11-16', '2026-11-22'))
        self.assertEqual([d['calories'] for d in data['days']],
                         [2100, 0, 0, 0, 0, 1800, 0])
        self.assertEqual(data['target'], {'calories': 2000})

    def test_meals_from_fatsecret(self):
        entries = {'food_entry': [
            {'meal': 'Lunch', 'calories': '500'},
            {'meal': 'Breakfast', 'calories': '300.4'},
            {'meal': 'Lunch', 'calories': '120'},
        ]}
        session = mock.patch('fatsecret.tools.fatsecret.get_session')
        fetch = mock.patch('fatsecret.tools.get_fatsecret_data',
                           return_value=entries)
        with session, fetch:
            meals = cards.meals_for(self.user, TODAY)
        self.assertEqual(meals, [{'name': 'Завтрак', 'calories': 300},
                                 {'name': 'Обед', 'calories': 620}])

    def test_meals_survive_fatsecret_errors(self):
        with mock.patch('fatsecret.tools.fatsecret.get_session',
                        side_effect=RuntimeError):
            self.assertEqual(cards.meals_for(self.user, TODAY), [])


@override_settings(TELEGRAM_REPORT_CARDS=True)
@mock.patch('tgbot.scheduler.time.sleep')
@mock.patch('tgbot.scheduler.refresh_diary')
@mock.patch('tgbot.cards.meals_for', return_value=[])
@mock.patch('tgbot.scheduler.send_message', return_value=SENT)
@mock.patch('tgbot.scheduler.send_photo', return_value=SENT)
class CardDeliveryTests(TestCase):

    def setUp(self):
        self.user = make_client()
        TelegramAccount.objects.create(user=self.user, telegram_id=TG_ID)
        DailyCheckin.objects.create(user=self.user, date=TODAY, sleep=3,
                                    wellbeing=3, stress=3, hunger=3)
        BodyStatsDiary.objects.create(user=self.user, date=TODAY, waist=80)
        eat(self.user, TODAY, weight=81.5)

    def test_report_goes_as_a_picture_with_caption(self, photo, text, *_):
        with mock.patch('tgbot.scheduler.CardRenderer') as renderer:
            renderer.return_value.render.return_value = b'jpeg'
            scheduler.run(now=moscow(TODAY, '21:05'))

        photo.assert_called_once()
        chat_id, jpeg, caption, button = photo.call_args.args
        self.assertEqual((chat_id, jpeg), (TG_ID, b'jpeg'))
        self.assertEqual(caption,
                         '📊 23 ноября · 1\u00a0900 / 2\u00a0000 ккал · '
                         '✅ в норме')
        self.assertEqual(button[1], '/stats?day=2026-11-23')
        text.assert_not_called()
        renderer.return_value.close.assert_called_once()

    def test_falls_back_to_text_when_drawing_fails(self, photo, text, *_):
        with mock.patch('tgbot.scheduler.CardRenderer') as renderer:
            renderer.return_value.render.return_value = None
            scheduler.run(now=moscow(TODAY, '21:05'))
        photo.assert_not_called()
        self.assertIn('Отчёт за 23 ноября', text.call_args.args[1])

    def test_reminders_stay_text(self, photo, text, *_):
        with mock.patch('tgbot.scheduler.CardRenderer'):
            DailyCheckin.objects.all().delete()
            scheduler.run(now=moscow(TODAY, '08:05'))
        photo.assert_not_called()
        text.assert_called_once()
