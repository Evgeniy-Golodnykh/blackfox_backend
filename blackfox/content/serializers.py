from django.db import transaction
from rest_framework import serializers

from content.models import Article, ArticleContent, Video

error_image_message = 'Please choose an image with a size less than 5 mb'
link_or_body_message = 'Нужен текст статьи или ссылка на неё.'


class VideoSerializer(serializers.ModelSerializer):
    """Serializer for Video model."""

    class Meta:
        model = Video
        fields = '__all__'


class ArticleSerializer(serializers.ModelSerializer):
    """Serializer for Article model.

    `has_body` — the article's text is stored here (ArticleContent) and
    the app opens it on its own screen. `body` is written by the admin and
    read only on the single-article endpoint (the list stays light).
    `link` may be empty when there is a body."""

    image = serializers.ImageField()
    link = serializers.URLField(max_length=200, required=False,
                                allow_blank=True)
    has_body = serializers.SerializerMethodField()
    body = serializers.CharField(required=False, allow_blank=True,
                                 write_only=True)

    class Meta:
        model = Article
        fields = ('id', 'title', 'link', 'section', 'image', 'has_body',
                  'body')

    def get_has_body(self, obj):
        content = getattr(obj, 'content', None)
        return bool(content and content.body.strip())

    def validate_image(self, value):
        if not value or value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(error_image_message)
        return value

    def validate(self, attrs):
        instance = self.instance
        link = attrs.get('link', instance.link if instance else '')
        if 'body' in attrs:
            body = attrs['body']
        else:
            content = getattr(instance, 'content', None) if instance else None
            body = content.body if content else ''
        if not (link or '').strip() and not (body or '').strip():
            raise serializers.ValidationError(link_or_body_message)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        body = validated_data.pop('body', None)
        validated_data.setdefault('link', '')
        article = super().create(validated_data)
        self._save_body(article, body)
        return article

    @transaction.atomic
    def update(self, instance, validated_data):
        body = validated_data.pop('body', None)
        article = super().update(instance, validated_data)
        self._save_body(article, body)
        return article

    @staticmethod
    def _save_body(article, body):
        if body is None:
            return
        if body.strip():
            ArticleContent.objects.update_or_create(
                article=article, defaults={'body': body.strip()})
        else:
            ArticleContent.objects.filter(article=article).delete()
        # Drop the cached reverse relation so has_body reads the new state.
        article._state.fields_cache.pop('content', None)


class ArticleDetailSerializer(ArticleSerializer):
    """GET /api/articles/<id>/ — the card plus its text."""

    body = serializers.SerializerMethodField()

    def get_body(self, obj):
        content = getattr(obj, 'content', None)
        return content.body if content else ''
