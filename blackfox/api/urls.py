"""URLs for API version 1.1"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView, TokenRefreshView,
)

from content.views import ArticleViewSet, VideoViewSet
from training.views import (
    BodyStatsDiaryViewSet, FoodDiaryViewSet, ProjectViewSet,
)
from users.views import CustomUserViewSet

router = DefaultRouter()
router.register('users', CustomUserViewSet, basename='user')
router.register('bodystats', BodyStatsDiaryViewSet, basename='bodystats')
router.register('fooddiary', FoodDiaryViewSet, basename='fooddiary')
router.register('project', ProjectViewSet, basename='project')
router.register('articles', ArticleViewSet, basename='article')
router.register('videos', VideoViewSet, basename='video')

urlpatterns = [
    path('signup/',
         CustomUserViewSet.as_view({'post': 'create'}),
         name='signup'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('fatsecret/', include('fatsecret.urls')),
    path('cycle/', include('cycles.urls')),
    path('', include(router.urls)),
]
