import datetime as dt
import os

from rauth import OAuth1Service

from training.models import FoodDiary, Project

CONSUMER_KEY = os.getenv('FATSECRET_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('FATSECRET_CONSUMER_SECRET')
REQUEST_TOKEN_URL = 'https://www.fatsecret.com/oauth/request_token'
AUTHORIZE_URL = 'https://www.fatsecret.com/oauth/authorize'
ACCESS_TOKEN_URL = 'https://www.fatsecret.com/oauth/access_token'
BASE_URL = 'https://platform.fatsecret.com/rest/server.api'
CALLBACK_URL = os.getenv('FATSECRET_CALLBACK_URL')

fatsecret = OAuth1Service(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    request_token_url=REQUEST_TOKEN_URL,
    access_token_url=ACCESS_TOKEN_URL,
    authorize_url=AUTHORIZE_URL,
    base_url=BASE_URL,
)
params_food = {'method': 'food_entries.get.v2', 'format': 'json'}
params_weight = {'method': 'weights.get_month.v2', 'format': 'json'}


def unix_date_converter(date):
    epoch = dt.date.fromtimestamp(0)
    if type(date) is str:
        return (dt.date.fromisoformat(date) - epoch).days
    if type(date) is int:
        return epoch + dt.timedelta(date)
    return (date - epoch).days


def food_caclulator(foods, weight, project, date):
    instance = {
        'user': project.user,
        'date': date,
        'calories_target': project.target_calories,
        'carbohydrate_target': project.target_carbohydrate,
        'fat_target': project.target_fat,
        'fiber_target': project.target_fiber,
        'protein_target': project.target_protein,
        'sugar_target': project.target_sugar,
        'weight_target': project.target_weight,
    }
    for food in foods:
        instance['calories_actual'] = (
            instance.get('calories_actual', 0)
            + int(food.get('calories', 0))
        )
        instance['carbohydrate_actual'] = round(
            (instance.get('carbohydrate_actual', 0)
             + float(food.get('carbohydrate', 0))),
            2
        )
        instance['fat_actual'] = round(
            (instance.get('fat_actual', 0)
             + float(food.get('fat', 0))),
            2
        )
        instance['fiber_actual'] = round(
            (instance.get('fiber_actual', 0)
             + float(food.get('fiber', 0))),
            2
        )
        instance['protein_actual'] = round(
            (instance.get('protein_actual', 0)
             + float(food.get('protein', 0))),
            2
        )
        instance['sugar_actual'] = round(
            (instance.get('sugar_actual', 0)
             + float(food.get('sugar', 0))),
            2
        )
        instance['weight_actual'] = weight if weight else 0
    return instance


def get_fatsecret_data(session, params, date, weight=False):
    params['date'] = unix_date_converter(date)
    fatsecret_data = session.get(BASE_URL, params=params).json()
    if fatsecret_data.get('error'):
        message = fatsecret_data.get('error').get('message')
        raise KeyError(message)
    if not weight:
        return fatsecret_data.get('food_entries')
    weights = {}
    monthly_weights = fatsecret_data['month'].get('day')
    if not monthly_weights:
        return weights
    for daily_weight in monthly_weights:
        weights[unix_date_converter(int(daily_weight['date_int']))] = float(
            daily_weight['weight_kg']
        )
    return weights


def get_fooddiary_objects(user):
    session = fatsecret.get_session(
        token=(user.fatsecret_token, user.fatsecret_secret)
    )
    fooddiary = FoodDiary.objects.filter(user=user).first()
    project = Project.objects.filter(user=user).first()
    if fooddiary:
        last_diary_date = fooddiary.date
        FoodDiary.objects.filter(id=fooddiary.id).delete()
    else:
        last_diary_date = project.start_date

    current_month = last_diary_date.month
    monthly_weights = get_fatsecret_data(
        session=session,
        params=params_weight,
        date=last_diary_date,
        weight=True
    )
    fooddiary_objects = []

    while last_diary_date <= dt.date.today():
        food_entries = get_fatsecret_data(
            session=session,
            params=params_food,
            date=last_diary_date
        )
        if last_diary_date.month != current_month:
            monthly_weights = get_fatsecret_data(
                session=session,
                params=params_weight,
                date=last_diary_date,
                weight=True
            )
            current_month = last_diary_date.month
        if food_entries:
            fooddiary_objects.append(
                FoodDiary(**food_caclulator(
                    foods=food_entries.get('food_entry'),
                    weight=monthly_weights.get(last_diary_date),
                    project=project,
                    date=last_diary_date
                ))
            )
        last_diary_date += dt.timedelta(1)

    session.close()
    return fooddiary_objects
