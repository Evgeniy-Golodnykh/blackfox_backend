"""URLs for connection to FatSecret API"""

from django.urls import path

from fatsecret_api.views import (
    AccessTokenView, FoodDiaryView, RequestTokenView, WeightDiaryView
)

urlpatterns = [
    path('request/', RequestTokenView.as_view(), name='request'),
    path('access/', AccessTokenView.as_view(), name='access'),
    path('foods/', FoodDiaryView.as_view(), name='foods'),
    path('weights/', WeightDiaryView.as_view(), name='weights'),
]
