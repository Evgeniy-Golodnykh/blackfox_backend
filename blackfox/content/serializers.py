from rest_framework import serializers

from content.models import Article, Video


class VideoSerializer(serializers.ModelSerializer):
    """Serializer for Video model."""

    class Meta:
        model = Video
        fields = '__all__'


class ArticleSerializer(serializers.ModelSerializer):
    """Serializer for Article model."""

    image = serializers.ImageField()

    class Meta:
        model = Article
        fields = '__all__'
