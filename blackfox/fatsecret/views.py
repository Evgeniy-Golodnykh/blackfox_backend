from django.core.cache import cache
from django.shortcuts import redirect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from fatsecret.tools import (
    BASE_URL, CALLBACK_URL, fatsecret, unix_date_converter,
)

error_date_message = 'Incorrect date format, should be YYYY-MM-DD or YYMMDD'
error_request_message = 'Missing FatSecret verification code or request tokens'
success_message = 'FatSecret account successfully linked'


class RequestTokenView(APIView):

    def get(self, request):
        request_token, request_token_secret = fatsecret.get_request_token(
            method='GET', params={'oauth_callback': CALLBACK_URL}
        )
        authorize_url = fatsecret.get_authorize_url(request_token)
        cache.set(request_token, (request_token_secret, request.user), 900)

        return Response(
            {'authorize_url': authorize_url},
            status=status.HTTP_200_OK
        )


class AccessTokenView(APIView):
    permission_classes = (AllowAny,)

    def get(self, request):
        verifier = request.query_params.get('oauth_verifier')
        request_token = request.query_params.get('oauth_token')
        request_token_secret, user = cache.get(request_token, (None, None))
        cache.delete(request_token)
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
        session.close()

        return Response(
            {'message': success_message},
            status=status.HTTP_200_OK
        )


class FatsecretDataView(APIView):
    params = None

    def get(self, request):
        access_token = request.user.fatsecret_token
        access_token_secret = request.user.fatsecret_secret
        if not access_token or not access_token_secret:
            return redirect('get_request_token')

        session = fatsecret.get_session(
            token=(access_token, access_token_secret)
        )

        date = request.query_params.get('date')
        if date:
            try:
                self.params['date'] = unix_date_converter(date)
            except ValueError:
                return Response(
                    {'message': error_date_message},
                    status=status.HTTP_400_BAD_REQUEST
                )

        fatsecret_data = session.get(BASE_URL, params=self.params).json()
        session.close()

        return Response(fatsecret_data, status=status.HTTP_200_OK)


class FoodDiaryMonthlyView(FatsecretDataView):
    params = {'method': 'food_entries.get_month.v2', 'format': 'json'}


class FoodDiaryDailyView(FatsecretDataView):
    params = {'method': 'food_entries.get.v2', 'format': 'json'}


class WeightDiaryView(FatsecretDataView):
    params = {'method': 'weights.get_month.v2', 'format': 'json'}
