"""URLs for API version 1."""

from django.urls import include, path
from djoser.views import UserViewSet
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView,
)

from api.views import BodyStatsDiaryViewSet, FoodDiaryViewSet, ProjectViewSet

router = DefaultRouter()
router.register(
    'bodystats_diary', BodyStatsDiaryViewSet, basename='bodystats_diary'
)
router.register('food_diary', FoodDiaryViewSet, basename='food_diary')
router.register('project', ProjectViewSet, basename='project')

urlpatterns = [
    path('signup/', UserViewSet.as_view({'post': 'create'}), name='signup'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('fatsecret/', include('fatsecret_api.urls')),
    path('', include('djoser.urls')),
    path('', include(router.urls)),
]
