import shutil
import tempfile
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from content.models import Article, ArticleContent
from content.telegraph import telegraph_path, to_body

User = get_user_model()
MEDIA = tempfile.mkdtemp()


def make(name, role=User.Roles.USER):
    return User.objects.create_user(
        username=name, email=f'{name}@example.com', password='Str0ng-pass-1',
        gender=User.Gender.FEMALE, role=role)


def picture(name='cover.jpg'):
    buf = BytesIO()
    Image.new('RGB', (4, 4), 'black').save(buf, 'JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


@override_settings(MEDIA_ROOT=MEDIA)
class ArticleApiTests(APITestCase):

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        self.anna = make('anna')
        self.admin = make('boss', role=User.Roles.ADMIN)
        self.outside = Article.objects.create(
            title='Снаружи', link='https://telegra.ph/A-01-01',
            section='Питание')
        self.inside = Article.objects.create(
            title='Внутри', link='', section='Сон')
        ArticleContent.objects.create(article=self.inside,
                                      body='Абзац.\n\n• пункт')

    def test_list_says_which_articles_open_inside_without_body(self):
        self.client.force_authenticate(self.anna)
        listed = self.client.get('/api/articles/').json()
        rows = {r['title']: r for r in listed}
        self.assertFalse(rows['Снаружи']['has_body'])
        self.assertTrue(rows['Внутри']['has_body'])
        self.assertNotIn('body', rows['Внутри'])

    def test_detail_has_the_text(self):
        self.client.force_authenticate(self.anna)
        data = self.client.get(f'/api/articles/{self.inside.id}/').json()
        self.assertEqual(data['body'], 'Абзац.\n\n• пункт')
        data = self.client.get(f'/api/articles/{self.outside.id}/').json()
        self.assertEqual(data['body'], '')

    def test_client_cannot_write(self):
        self.client.force_authenticate(self.anna)
        r = self.client.patch(f'/api/articles/{self.inside.id}/',
                              {'body': 'x'})
        self.assertEqual(r.status_code, 403)

    def test_admin_creates_article_with_text_and_no_link(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/articles/', {
            'title': 'Новая', 'section': 'Сон', 'body': 'Текст статьи',
            'image': picture()}, format='multipart')
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.json()['has_body'])
        article = Article.objects.get(title='Новая')
        self.assertEqual(article.link, '')
        self.assertEqual(article.content.body, 'Текст статьи')

    def test_needs_link_or_text(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/articles/', {
            'title': 'Пустая', 'section': 'Сон', 'image': picture()},
            format='multipart')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f'/api/articles/{self.inside.id}/', {'body': ''})
        self.assertEqual(r.status_code, 400)  # no link to fall back on

    def test_admin_edits_and_removes_text(self):
        self.client.force_authenticate(self.admin)
        r = self.client.patch(f'/api/articles/{self.outside.id}/',
                              {'body': 'Перенесли к себе'})
        self.assertTrue(r.json()['has_body'])
        self.assertEqual(ArticleContent.objects.get(article=self.outside).body,
                         'Перенесли к себе')
        r = self.client.patch(f'/api/articles/{self.outside.id}/',
                              {'body': ''})
        self.assertFalse(r.json()['has_body'])
        self.assertFalse(
            ArticleContent.objects.filter(article=self.outside).exists())

    def test_patch_without_body_keeps_text(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(f'/api/articles/{self.inside.id}/',
                          {'title': 'Сон и вес'})
        self.assertEqual(ArticleContent.objects.get(article=self.inside).body,
                         'Абзац.\n\n• пункт')


class TelegraphTests(APITestCase):

    NODES = [
        {'tag': 'figure', 'children': [
            {'tag': 'img', 'attrs': {'src': '/file/abc.jpg'}},
            {'tag': 'figcaption', 'children': ['Подпись']}]},
        {'tag': 'p', 'children': ['Первый ',
                                  {'tag': 'b', 'children': ['жирный']},
                                  {'tag': 'br'}, 'абзац']},
        {'tag': 'h3', 'children': ['Раздел']},
        {'tag': 'ul', 'children': [
            {'tag': 'li', 'children': ['один']},
            {'tag': 'li', 'children': [{'tag': 'a', 'attrs': {'href': 'x'},
                                        'children': ['два']}]}]},
        {'tag': 'blockquote', 'children': ['Цитата']},
        {'tag': 'hr'},
        {'tag': 'figure', 'children': [{'tag': 'iframe', 'attrs': {
            'src': '/embed/youtube?url=https%3A%2F%2Fyoutu.be%2Fxyz'}}]},
    ]

    def test_path(self):
        self.assertEqual(telegraph_path('https://telegra.ph/Pitanie-01-15'),
                         'Pitanie-01-15')
        self.assertIsNone(telegraph_path('https://example.com/a'))
        self.assertIsNone(telegraph_path(''))

    def test_nodes_to_body(self):
        saved = []
        body = to_body(self.NODES,
                       lambda url: saved.append(url) or '/media/1.jpg')
        self.assertEqual(saved, ['https://telegra.ph/file/abc.jpg'])
        self.assertEqual(body, '\n\n'.join([
            '![Подпись](/media/1.jpg)',
            'Первый жирный абзац',
            '## Раздел',
            '• один\n• два',
            '> Цитата',
            'Видео: https://youtu.be/xyz',
        ]))

    def test_command_imports_only_telegraph_and_keeps_existing(self):
        a = Article.objects.create(
            title='T', link='https://telegra.ph/T-01-01', section='S')
        b = Article.objects.create(title='O', link='https://example.com/o',
                                   section='S')
        c = Article.objects.create(
            title='Done', link='https://telegra.ph/D-01-01', section='S')
        ArticleContent.objects.create(article=c, body='свой текст')
        page = {'content': [{'tag': 'p', 'children': ['Текст']}]}
        with mock.patch('content.management.commands.import_telegraph_articles'
                        '.fetch_page', return_value=page) as fetch:
            call_command('import_telegraph_articles', stdout=BytesIOText(),
                         stderr=BytesIOText())
        fetch.assert_called_once_with('T-01-01')
        self.assertEqual(ArticleContent.objects.get(article=a).body, 'Текст')
        self.assertFalse(ArticleContent.objects.filter(article=b).exists())
        self.assertEqual(ArticleContent.objects.get(article=c).body,
                         'свой текст')


class BytesIOText:
    def write(self, *_):
        pass

    def flush(self):
        pass
