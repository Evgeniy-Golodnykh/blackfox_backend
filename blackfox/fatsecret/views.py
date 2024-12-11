from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.shortcuts import get_object_or_404, redirect
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from fatsecret.tools import (
    BLACKFOX_URL, CALLBACK_URL, PARAMS_FOOD_DAILY, PARAMS_FOOD_MONTHLY,
    PARAMS_WEIGHT, fatsecret, unix_date_converter,
)

User = get_user_model()

error_date_message = 'Incorrect date format, should be YYYY-MM-DD or YYYYMMDD'
error_request_message = 'Missing FatSecret verification code or request tokens'
fatsecret_account_not_exists_message = 'Please link your Fatsecret account'


class RequestTokenView(APIView):
    """A view to request FatSecret token."""

    def get(self, request):
        request_token, request_token_secret = fatsecret.get_request_token(
            method='GET', params={'oauth_callback': CALLBACK_URL}
        )
        authorize_url = fatsecret.get_authorize_url(request_token)
        cache.set(request_token, (request_token_secret, request.user), 300)
        return Response(
            {'authorize_url': authorize_url},
            status=status.HTTP_200_OK
        )


class AccessTokenView(APIView):
    """A view to access FatSecret token."""

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
        return redirect(BLACKFOX_URL)


class FatsecretDataView(APIView):
    """A view for obtaining FatSecret user data."""

    params = None

    def get(self, request):
        if request.user.is_admin or request.user.is_coach:
            user = get_object_or_404(
                User, username=request.query_params.get('user')
            )
        else:
            user = request.user
        access_token = user.fatsecret_token
        access_token_secret = user.fatsecret_secret
        if not access_token or not access_token_secret:
            return Response(
                {'message': fatsecret_account_not_exists_message},
                status=status.HTTP_400_BAD_REQUEST
            )
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
        fatsecret_data = session.get(fatsecret.base_url, params=self.params)
        session.close()
        return Response(fatsecret_data.json(), status=status.HTTP_200_OK)


class FoodDiaryDailyView(FatsecretDataView):
    params = PARAMS_FOOD_DAILY


class FoodDiaryMonthlyView(FatsecretDataView):
    params = PARAMS_FOOD_MONTHLY


class WeightDiaryView(FatsecretDataView):
    params = PARAMS_WEIGHT
