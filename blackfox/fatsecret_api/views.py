import os

from django.core.cache import cache
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rauth import OAuth1Service

CONSUMER_KEY = os.getenv('FATSECRET_CONSUMER_KEY')
CONSUMER_SECRET = os.getenv('FATSECRET_CONSUMER_SECRET')
REQUEST_TOKEN_URL = 'https://www.fatsecret.com/oauth/request_token'
AUTHORIZE_URL = 'https://www.fatsecret.com/oauth/authorize'
ACCESS_TOKEN_URL = 'https://www.fatsecret.com/oauth/access_token'
BASE_URL = 'https://platform.fatsecret.com/rest/server.api'
CALLBACK_URL = os.getenv('FATSECRET_CALLBACK_URL')

error_access_message = 'Missing FatSecret access tokens'
error_request_message = 'Missing FatSecret verification code or request tokens'
success_message = 'FatSecret account successfully linked'

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
            method='GET', params={'oauth_callback': CALLBACK_URL}
        )
        authorize_url = fatsecret.get_authorize_url(request_token)
        cache.set('request_token', request_token)
        cache.set('request_token_secret', request_token_secret)
        cache.set('user', request.user)
        return Response(
            {'authorize_url': authorize_url},
            status=status.HTTP_200_OK
        )


class AccessTokenView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        verifier = request.query_params.get('oauth_verifier')
        request_token = cache.get('request_token')
        request_token_secret = cache.get('request_token_secret')
        user = cache.get('user')
        cache.clear()
        if not verifier or not request_token or not request_token_secret:
            return Response(
                {'message': error_request_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        session = fatsecret.get_auth_session(
            request_token, request_token_secret,
            method='POST', data={'oauth_verifier': verifier}
        )
        user.fatsecret_token = session.access_token
        user.fatsecret_secret = session.access_token_secret
        user.save()

        return Response(
            {'message': success_message},
            status=status.HTTP_200_OK
        )


class FoodDiaryView(APIView):

    def get(self, request):
        access_token = request.user.fatsecret_token
        access_token_secret = request.user.fatsecret_secret
        if not access_token or not access_token_secret:
            return Response(
                {'message': error_access_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        session = fatsecret.get_session(
            token=(access_token, access_token_secret)
        )
        params = {'method': 'food_entries.get_month.v2', 'format': 'json'}

        return Response(
            session.get(BASE_URL, params=params).json(),
            status=status.HTTP_200_OK
        )


class WeightDiaryView(APIView):

    def get(self, request):
        access_token = request.user.fatsecret_token
        access_token_secret = request.user.fatsecret_secret
        if not access_token or not access_token_secret:
            return Response(
                {'message': error_access_message},
                status=status.HTTP_400_BAD_REQUEST
            )
        session = fatsecret.get_session(
            token=(access_token, access_token_secret)
        )
        params = {'method': 'weights.get_month.v2', 'format': 'json'}

        return Response(
            session.get(BASE_URL, params=params).json(),
            status=status.HTTP_200_OK
        )
