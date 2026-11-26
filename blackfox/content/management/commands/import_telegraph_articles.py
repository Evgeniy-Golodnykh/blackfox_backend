from django.core.management.base import BaseCommand

from content.models import Article, ArticleContent
from content.telegraph import fetch_page, image_saver, telegraph_path, to_body


class Command(BaseCommand):
    help = ('Переносит тексты статей библиотеки с telegra.ph на наш сервер '
            '(таблица ArticleContent, картинки — в media/article_content/). '
            'Ссылка в карточке остаётся как источник.')

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, action='append',
                            help='Только эти статьи (можно несколько раз).')
        parser.add_argument('--force', action='store_true',
                            help='Перезаписать уже перенесённый текст.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Только показать, что будет перенесено.')

    def handle(self, *args, **options):
        articles = Article.objects.select_related('content').order_by('id')
        if options['id']:
            articles = articles.filter(id__in=options['id'])

        done = skipped = failed = 0
        for article in articles:
            path = telegraph_path(article.link)
            label = f'#{article.id} «{article.title}»'
            if not path:
                self.stdout.write(
                    f'— {label}: не telegra.ph ({article.link}), пропуск')
                skipped += 1
                continue
            if hasattr(article, 'content') and not options['force']:
                self.stdout.write(f'— {label}: текст уже есть, пропуск')
                skipped += 1
                continue
            if options['dry_run']:
                self.stdout.write(f'· {label}: будет перенесена из {path}')
                continue
            try:
                page = fetch_page(path)
                body = to_body(page.get('content'),
                               image_saver(f'article_content/{article.id}'))
            except Exception as error:  # noqa: BLE001 — report and go on
                self.stderr.write(f'✗ {label}: {error}')
                failed += 1
                continue
            if not body.strip():
                self.stderr.write(f'✗ {label}: пустой текст')
                failed += 1
                continue
            ArticleContent.objects.update_or_create(
                article=article, defaults={'body': body})
            self.stdout.write(self.style.SUCCESS(
                f'✓ {label}: {len(body)} символов'))
            done += 1

        self.stdout.write(f'Перенесено: {done}, пропущено: {skipped}, '
                          f'ошибок: {failed}')
