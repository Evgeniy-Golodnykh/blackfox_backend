from rest_framework import serializers

from content.models import Article, Video

error_image_message = 'Please choose an image with a size less than 5 mb'


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

    def validate_image(self, value):
        if not value or value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(error_image_message)
        return value
