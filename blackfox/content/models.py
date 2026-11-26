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


class ArticleContent(models.Model):
    """The text of a library article, kept on our server so the app shows
    it on its own screen instead of opening the outside link. A separate
    table — Article itself stays as it was. No row → the app falls back
    to Article.link.

    Format (the same simple one as course lessons, plus two marks):
    paragraphs split by a blank line; a line starting with «• » is a
    bullet; «## » starts a heading; a line «![подпись](/media/…)» is a
    picture."""

    article = models.OneToOneField(Article, on_delete=models.CASCADE,
                                   primary_key=True, related_name='content',
                                   verbose_name='статья')
    body = models.TextField(
        verbose_name='текст',
        help_text='Абзацы — через пустую строку; «• » — пункт списка; '
                  '«## » — подзаголовок; строка «![подпись](ссылка)» — '
                  'картинка.')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='изменён')

    class Meta:
        verbose_name = 'Текст статьи'
        verbose_name_plural = 'Тексты статей'

    def __str__(self):
        return f'Текст: {self.article}'
