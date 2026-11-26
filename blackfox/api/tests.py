import importlib
import os
from unittest import mock

from rest_framework.test import APITestCase


class DebugOffTests(APITestCase):
    """The debug error page lists every API route — never on the server."""

    def settings_with(self, env):
        from blackfox import settings
        with mock.patch.dict(os.environ, env, clear=False):
            if 'DEBUG' not in env:
                os.environ.pop('DEBUG', None)
            return importlib.reload(settings)

    def tearDown(self):
        from blackfox import settings
        importlib.reload(settings)

    def test_debug_is_off_unless_asked_for(self):
        self.assertFalse(self.settings_with({}).DEBUG)
        self.assertFalse(self.settings_with({'DEBUG': 'False'}).DEBUG)
        self.assertTrue(self.settings_with({'DEBUG': 'True'}).DEBUG)

    def test_not_found_does_not_show_the_routes(self):
        response = self.client.get('/api/no-such-thing/')
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b'Page not found at', response.content)
        self.assertNotIn(b'URLconf', response.content)
