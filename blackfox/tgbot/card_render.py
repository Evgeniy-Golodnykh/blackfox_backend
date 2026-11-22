"""Draw the picture report: headless Chromium opens tgbot/card/card.html,
calls window.renderCard(data) and screenshots #card as a 1080×1920 JPEG.

One browser per run (CardRenderer as a context manager); any failure
returns None, and the caller sends the text version instead.
"""

import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

TEMPLATE = Path(__file__).resolve().parent / 'card' / 'card.html'


class CardRenderer:

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._broken = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _start(self):
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            executable_path=settings.CARD_CHROMIUM_PATH or None,
            # Runs as root in the container.
            args=['--no-sandbox', '--disable-dev-shm-usage'],
        )

    def render(self, data):
        """JPEG bytes, or None if it couldn't be drawn."""

        if self._broken:
            return None
        try:
            if self._browser is None:
                self._start()
            page = self._browser.new_page(
                viewport={'width': 540, 'height': 960},
                device_scale_factor=2,
            )
            try:
                page.add_init_script('window.__CARD_EXTERNAL__ = true')
                page.goto(TEMPLATE.as_uri())
                page.evaluate('data => window.renderCard(data)', data)
                return page.locator('#card').screenshot(type='jpeg',
                                                        quality=90)
            finally:
                page.close()
        except Exception as err:
            # Chromium missing or crashing: don't retry for every message.
            logger.warning('Report card render failed: %s',
                           type(err).__name__)
            self._broken = self._browser is None
            return None

    def close(self):
        try:
            if self._browser is not None:
                self._browser.close()
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:  # closing a crashed browser — nothing to do
            pass
        self._browser = self._playwright = None
