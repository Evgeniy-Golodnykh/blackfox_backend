import os

from rest_framework.views import APIView
from rest_framework.response import Response
from rauth import OAuth1Service

CONSUMER_KEY = os.getenv('FATSECRET_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('FATSECRET_CONSUMER_SECRET')
REQUEST_TOKEN_URL = 'https://www.fatsecret.com/oauth/request_token'
AUTHORIZE_URL = 'https://www.fatsecret.com/oauth/authorize'
ACCESS_TOKEN_URL = 'https://www.fatsecret.com/oauth/access_token'
BASE_URL = 'https://platform.fatsecret.com/rest/server.api'

print(CONSUMER_KEY, CONSUMER_SECRET, sep='\n---\n')

fatsecret = OAuth1Service(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    request_token_url=REQUEST_TOKEN_URL,
    access_token_url=ACCESS_TOKEN_URL,
    authorize_url=AUTHORIZE_URL,
    base_url=BASE_URL,
)


class RequestTokenView(APIView):
    def get(self, request):
        request_token, request_token_secret = fatsecret.get_request_token(
            method='GET', params={'oauth_callback': 'oob'}
        )
        authorize_url = fatsecret.get_authorize_url(request_token)
        request.session['request_token'] = request_token
        request.session['request_token_secret'] = request_token_secret
        return Response({'authorize_url': authorize_url})
