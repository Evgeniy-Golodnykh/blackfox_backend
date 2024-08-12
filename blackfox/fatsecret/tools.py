import datetime as dt
import os

from django.shortcuts import redirect
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
    if type(date) is int:
        return epoch + dt.timedelta(date)
    return (date - epoch).days


def food_caclulator(foods, instance):
    for food in foods:
        instance['calories_actual'] = (
            instance.get('calories_actual', 0) + int(food.get('calories', 0))
        )
        instance['carbohydrate_actual'] = (
            instance.get('carbohydrate_actual', 0)
            + float(food.get('carbohydrate', 0))
        )
        instance['fat_actual'] = (
            instance.get('fat_actual', 0) + float(food.get('fat', 0))
        )
        instance['fiber_actual'] = (
            instance.get('fiber_actual', 0) + float(food.get('fiber', 0))
        )
        instance['protein_actual'] = (
            instance.get('protein_actual', 0) + float(food.get('protein', 0))
        )
        instance['sugar_actual'] = (
            instance.get('sugar_actual', 0) + float(food.get('sugar', 0))
        )
    return instance


def get_fatsecret_data(user):
    fooddiary = FoodDiary.objects.filter(user=user).first()
    project = Project.objects.filter(user=user).first()
    if fooddiary:
        last_date = fooddiary.date
        FoodDiary.objects.filter(id=fooddiary.id).delete()
    else:
        last_date = project.start_date
    current_date = dt.date.today()

    instance = {
        'user': user,
        'calories_target': project.target_calories,
        'carbohydrate_target': project.target_carbohydrate,
        'fat_target': project.target_fat,
        'fiber_target': project.target_fiber,
        'protein_target': project.target_protein,
        'sugar_target': project.target_sugar,
    }

    access_token = user.fatsecret_token
    access_token_secret = user.fatsecret_secret
    if not access_token or not access_token_secret:
        return redirect('get_request_token')   # зарайзить ValidationError
    session = fatsecret.get_session(
        token=(access_token, access_token_secret)
    )

    params = {'method': 'food_entries.get.v2', 'format': 'json'}
    objects = []
    while last_date <= current_date:
        params['date'] = (last_date - dt.date.fromtimestamp(0)).days
        fatsecret_data = session.get(BASE_URL, params=params).json()
        food_entries = fatsecret_data.get('food_entries')
        if food_entries:
            instance['date'] = last_date
            objects.append(
                FoodDiary(**food_caclulator(
                    food_entries.get('food_entry'), instance
                ))
            )
        last_date += dt.timedelta(1)
    session.close()
    return objects
