import datetime as dt
import os

from django.shortcuts import redirect
from rauth import OAuth1Service

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
    return (dt.date.fromisoformat(date) - epoch).days


def get_fatsecret_data(user):
    access_token = user.fatsecret_token
    access_token_secret = user.fatsecret_secret
    if not access_token or not access_token_secret:
        return redirect('get_request_token')

    session = fatsecret.get_session(
        token=(access_token, access_token_secret)
    )
    # params = {'method': 'food_entries.get_month.v2', 'format': 'json'}
    param = {'method': 'weights.get_month.v2', 'format': 'json', 'date': 19900}
    param = {'method': 'food_entries.get.v2', 'format': 'json', 'date': 19900}
    fatsecret_data = session.get(BASE_URL, params=param).json()
    session.close()
    food_entries = fatsecret_data.get('food_entries', None)
    if food_entries:
        return food_entries.get('food_entry', None)
    return food_entries
