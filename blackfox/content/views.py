from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from api.permissions import IsAdmin
from content.models import Article, Video
from content.serializers import ArticleSerializer, VideoSerializer


class ArticleViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Article instances."""

    queryset = Article.objects.all()
    serializer_class = ArticleSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdmin()]


class VideoViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Video instances."""

    queryset = Video.objects.all()
    serializer_class = VideoSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsAdmin()]
