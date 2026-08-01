from django.db import models


class Video(models.Model):
    """Video model for YouTube content"""

    title = models.CharField(max_length=200, verbose_name='название')
    youtube_id = models.URLField(max_length=200, verbose_name='ссылка')

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title


class Article(models.Model):
    """Article model for text content"""

    title = models.CharField(max_length=200, verbose_name='название')
    link = models.URLField(max_length=200, verbose_name='ссылка')
    section = models.CharField(max_length=200, verbose_name='раздел')
    image = models.ImageField(
        upload_to='article_images/',
        verbose_name='изображение',
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ['title']

    def __str__(self):
        return self.title
