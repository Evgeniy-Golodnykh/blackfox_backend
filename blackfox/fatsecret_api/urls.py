"""URLs for connection to FatSecret API"""

from django.urls import path

from fatsecret_api.views import (
    AccessTokenView, FoodDiaryView, RequestTokenView, WeightDiaryView
)

urlpatterns = [
    path('request/', RequestTokenView.as_view(), name='get_request_token'),
    path('access/', AccessTokenView.as_view(), name='get_access_token'),
    path('foods/', FoodDiaryView.as_view(), name='get_foods'),
    path('weights/', WeightDiaryView.as_view(), name='get_weights'),
]
