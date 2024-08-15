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


def unix_date_converter(date):
    epoch = dt.date.fromtimestamp(0)
    if type(date) is str:
        return (dt.date.fromisoformat(date) - epoch).days
    return (date - epoch).days


def food_caclulator(foods, project, date):
    instance = {
        'user': project.user,
        'date': date,
        'calories_target': project.target_calories,
        'carbohydrate_target': project.target_carbohydrate,
        'fat_target': project.target_fat,
        'fiber_target': project.target_fiber,
        'protein_target': project.target_protein,
        'sugar_target': project.target_sugar,
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
    return instance


def get_fooddiary_objects(user):
    fooddiary = FoodDiary.objects.filter(user=user).first()
    project = Project.objects.filter(user=user).first()
    if fooddiary:
        last_date = fooddiary.date
        FoodDiary.objects.filter(id=fooddiary.id).delete()
    else:
        last_date = project.start_date
    current_date = dt.date.today()

    session = fatsecret.get_session(
        token=(user.fatsecret_token, user.fatsecret_secret)
    )
    params = {'method': 'food_entries.get.v2', 'format': 'json'}

    fooddiary_objects = []
    while last_date <= current_date:
        params['date'] = unix_date_converter(last_date)
        fatsecret_data = session.get(BASE_URL, params=params).json()
        food_entries = fatsecret_data.get('food_entries')
        if food_entries:
            fooddiary_objects.append(
                FoodDiary(**food_caclulator(
                    food_entries.get('food_entry'), project, last_date
                ))
            )
        last_date += dt.timedelta(1)
    session.close()

    return fooddiary_objects
