"""URLs for API version 1."""

from django.urls import include, path
from djoser.views import UserViewSet
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView,
)
from rest_framework.routers import DefaultRouter

from api.fatsecret_views import RequestTokenView
from api.views import DietViewSet, MeasurementViewSet, ProjectViewSet


router = DefaultRouter()
router.register('diet', DietViewSet, basename='diet')
router.register('measurement', MeasurementViewSet, basename='measurement')
router.register('project', ProjectViewSet, basename='project')

urlpatterns = [
    path('signup/', UserViewSet.as_view({'post': 'create'}), name='signup'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', include('djoser.urls')),
    path('fatsecret/request/', RequestTokenView.as_view(), name='request'),
    path('', include(router.urls)),
]
