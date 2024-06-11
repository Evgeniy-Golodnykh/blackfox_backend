"""URLs for connection to FatSecret API"""

from django.urls import path
from fatsecret_api.views import (
    AccessTokenView, FoodDiaryDailyView, FoodDiaryMonthlyView,
    RequestTokenView, WeightDiaryView,
)

urlpatterns = [
    path('request/', RequestTokenView.as_view(), name='get_request_token'),
    path('access/', AccessTokenView.as_view(), name='get_access_token'),
    path('weights/', WeightDiaryView.as_view(), name='weights'),
    path('foods_daily/', FoodDiaryDailyView.as_view(), name='foods_daily'),
    path('foods_mothly/', FoodDiaryMonthlyView.as_view(), name='foods_monthly')
]
