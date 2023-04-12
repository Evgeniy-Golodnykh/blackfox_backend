"""URLs for API version 1."""

from django.urls import include, path
from rest_framework import routers
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView, LoginView, MeView, SignUpView, UserViewSet,
)

router_v1 = routers.DefaultRouter()
router_v1.register('users', UserViewSet)

urlpatterns = [
    path('signup/', SignUpView.as_view(), name='signup'),
    path('login/', LoginView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('users/me/', MeView.as_view()),
    path('users/me/change_password/', ChangePasswordView.as_view()),
    path('', include(router_v1.urls)),
]
