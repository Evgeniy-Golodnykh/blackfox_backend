from django.conf import settings
from rest_framework import serializers

from content.models import Article, Video


class VideoSerializer(serializers.ModelSerializer):
    """Serializer for Video model."""

    class Meta:
        model = Video
        fields = '__all__'


class ArticleSerializer(serializers.ModelSerializer):
    """Serializer for Article model."""

    image = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Article
        fields = '__all__'

    def get_image(self, obj):
        if obj.image:
            return f'{settings.BASE_URL}{settings.MEDIA_URL}{obj.image.name}'
        return None
