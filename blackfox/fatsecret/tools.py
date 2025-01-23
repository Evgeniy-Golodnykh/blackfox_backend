import datetime as dt
import os
from collections import Counter

from rauth import OAuth1Service

from training.models import FoodDiary, Project

CONSUMER_KEY = os.getenv('FATSECRET_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('FATSECRET_CONSUMER_SECRET')
REQUEST_TOKEN_URL = 'https://authentication.fatsecret.com/oauth/request_token'
ACCESS_TOKEN_URL = 'https://authentication.fatsecret.com/oauth/access_token'
AUTHORIZE_URL = 'https://authentication.fatsecret.com/oauth/authorize'
BASE_URL = 'https://platform.fatsecret.com/rest/server.api'
BLACKFOX_URL = 'https://www.blackfoxnutrition.ru/settings'
CALLBACK_URL = os.getenv('FATSECRET_CALLBACK_URL')
PARAMS_FOOD_DAILY = {'method': 'food_entries.get.v2', 'format': 'json'}
PARAMS_FOOD_MONTHLY = {'method': 'food_entries.get_month.v2', 'format': 'json'}
PARAMS_WEIGHT = {'method': 'weights.get_month.v2', 'format': 'json'}
FOOD_FIELDS = ['calories', 'carbohydrate', 'fat', 'fiber', 'protein', 'sugar']


fatsecret = OAuth1Service(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    request_token_url=REQUEST_TOKEN_URL,
    access_token_url=ACCESS_TOKEN_URL,
    authorize_url=AUTHORIZE_URL,
    base_url=BASE_URL,
)


def unix_date_converter(date):
    """A function to convert date to/from FatSceret format."""

    epoch = dt.date.fromtimestamp(0)
    if type(date) is str:
        return (dt.date.fromisoformat(date) - epoch).days
    if type(date) is int:
        return epoch + dt.timedelta(date)
    return (date - epoch).days


def daily_food_caclulator(foods, weight, project, date):
    """A function for calculating and compiling a daily food diary."""

    instance = {
        'user': project.user,
        'date': date,
        'calories_target': project.target_calories,
        'carbohydrate_target': project.target_carbohydrate,
        'fat_target': project.target_fat,
        'fiber_target': project.target_fiber,
        'protein_target': project.target_protein,
        'sugar_target': project.target_sugar,
        'weight_actual': weight if weight else 0,
        'weight_target': project.target_weight,
    }
    for food in foods:
        for field in FOOD_FIELDS:
            key = f'{field}_actual'
            instance[key] = round(
                instance.get(key, 0) + float(food.get(field, 0)), 2
            )
    return instance


def unique_food_nutrients_caclulator(daily_foods, sum_foods):
    """A function for calculating nutrients of unique food."""

    for food in daily_foods:
        food_entry_name = food.get('food_entry_name')
        food_params = {
            key: round(float(food.get(key, 0))) for key in FOOD_FIELDS
        }
        accumulated_food = Counter(sum_foods.get(food_entry_name))
        accumulated_food.update(Counter(food_params))
        sum_foods[food_entry_name] = dict(accumulated_food)
    return sum_foods


def get_fatsecret_data(session, params, date):
    """A function for obtaining FatSecret user data."""

    params['date'] = unix_date_converter(date)
    fatsecret_data = session.get(BASE_URL, params=params).json()
    if fatsecret_data.get('error'):
        message = fatsecret_data.get('error').get('message')
        raise KeyError(message)
    if params['method'] is PARAMS_FOOD_DAILY['method']:
        return fatsecret_data.get('food_entries')
    monthly_weights = fatsecret_data['month'].get('day')
    return dict() if not monthly_weights else {
        unix_date_converter(int(daily_weight['date_int'])):
        float(daily_weight['weight_kg'])
        for daily_weight in monthly_weights
    }


def get_fooddiary_objects(user, reload=False):
    """A function to create FoodDiary instance from fatscrit data."""

    fooddiary = FoodDiary.objects.filter(user=user).first()
    project = Project.objects.filter(user=user).first()
    if reload:
        last_diary_date = project.start_date
        FoodDiary.objects.filter(user=user).delete()
    elif fooddiary:
        last_diary_date = fooddiary.date
        FoodDiary.objects.filter(id=fooddiary.id).delete()
    else:
        last_diary_date = project.start_date
    session = fatsecret.get_session(
        token=(user.fatsecret_token, user.fatsecret_secret)
    )
    fooddiary_objects = []
    last_diary_month = last_diary_date.month
    monthly_weights = get_fatsecret_data(
        session=session,
        params=PARAMS_WEIGHT,
        date=last_diary_date
    )

    while last_diary_date <= dt.date.today():
        daily_foods = get_fatsecret_data(
            session=session,
            params=PARAMS_FOOD_DAILY,
            date=last_diary_date
        )
        if last_diary_date.month != last_diary_month:
            monthly_weights = get_fatsecret_data(
                session=session,
                params=PARAMS_WEIGHT,
                date=last_diary_date
            )
            last_diary_month = last_diary_date.month
        if daily_foods:
            fooddiary_objects.append(
                FoodDiary(**daily_food_caclulator(
                    foods=daily_foods.get('food_entry'),
                    weight=monthly_weights.get(last_diary_date),
                    project=project,
                    date=last_diary_date
                ))
            )
        last_diary_date += dt.timedelta(1)

    session.close()
    return fooddiary_objects


def get_weekly_food_nutrients(user):
    """A function for obtaining weekly foods nutrients."""

    session = fatsecret.get_session(
        token=(user.fatsecret_token, user.fatsecret_secret)
    )
    current_date = dt.date.today()
    last_diary_date = current_date - dt.timedelta(7)
    weekly_foods = {}

    while last_diary_date < current_date:
        daily_foods = get_fatsecret_data(
            session=session,
            params=PARAMS_FOOD_DAILY,
            date=last_diary_date
        )
        if daily_foods:
            weekly_foods = unique_food_nutrients_caclulator(
                daily_foods.get('food_entry'), weekly_foods
            )
        last_diary_date += dt.timedelta(1)

    session.close()
    return weekly_foods
