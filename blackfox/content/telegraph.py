"""Turning a telegra.ph page into an ArticleContent body.

telegra.ph has a public read API: GET https://api.telegra.ph/getPage/<path>
?return_content=true gives the page as a tree of nodes — a node is either
a string or {"tag": …, "attrs": {…}, "children": [nodes]}. We keep the
text, headings, lists, quotes and pictures (downloaded to our own media),
in the body format described on ArticleContent."""

import os
import re
from urllib.parse import urljoin, urlparse

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

API_URL = 'https://api.telegra.ph/getPage/{path}?return_content=true'
SITE = 'https://telegra.ph'
TIMEOUT = 20
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {'image/jpeg': '.jpg', 'image/png': '.png',
               'image/webp': '.webp', 'image/gif': '.gif'}


def telegraph_path(link):
    """'https://telegra.ph/Some-Page-01-15' → 'Some-Page-01-15', else None."""
    parsed = urlparse((link or '').strip())
    if parsed.hostname not in ('telegra.ph', 'www.telegra.ph', 'graph.org'):
        return None
    path = parsed.path.strip('/')
    return path or None


def fetch_page(path):
    response = requests.get(API_URL.format(path=path), timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    if not data.get('ok'):
        raise ValueError(data.get('error') or 'страница не найдена')
    return data['result']


def _text(nodes):
    """Inline text of a node list, one line (breaks become spaces)."""
    parts = []
    for node in nodes or []:
        if isinstance(node, str):
            parts.append(node)
        elif node.get('tag') == 'br':
            parts.append(' ')
        else:
            parts.append(_text(node.get('children')))
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()


def _media_src(node):
    """The src of the first img/iframe/video inside a node."""
    if isinstance(node, str):
        return None, None
    tag = node.get('tag')
    if tag in ('img', 'iframe', 'video'):
        return tag, (node.get('attrs') or {}).get('src')
    for child in node.get('children') or []:
        found = _media_src(child)
        if found[1]:
            return found
    return None, None


def _caption(node):
    for child in node.get('children') or []:
        if isinstance(child, dict) and child.get('tag') == 'figcaption':
            return _text(child.get('children'))
    return ''


def _video_url(src):
    """telegra.ph embeds look like /embed/youtube?url=<encoded>."""
    from urllib.parse import parse_qs
    parsed = urlparse(src)
    url = parse_qs(parsed.query).get('url', [None])[0]
    return url or urljoin(SITE, src)


def _plain_block(prefix=''):
    def convert(node, save_image):
        text = _text(node.get('children'))
        return f'{prefix}{text}' if text else None
    return convert


def _list_block(node, save_image):
    items = [_text(li.get('children')) for li in node.get('children') or []
             if isinstance(li, dict)]
    items = [i for i in items if i]
    return '\n'.join(f'• {i}' for i in items) or None


def _media_block(node, save_image):
    kind, src = _media_src(node)
    caption = _caption(node) if node.get('tag') == 'figure' else ''
    if kind == 'img' and src:
        url = save_image(urljoin(SITE, src))
        if url:
            return f'![{caption}]({url})'
    elif kind in ('iframe', 'video') and src:
        return f'{caption or "Видео"}: {_video_url(src)}'
    return caption or None


BLOCKS = {
    'p': _plain_block(),
    'pre': _plain_block(),
    'h3': _plain_block('## '),
    'h4': _plain_block('## '),
    'blockquote': _plain_block('> '),
    'aside': _plain_block('> '),
    'ul': _list_block,
    'ol': _list_block,
    'figure': _media_block,
    'img': _media_block,
    'iframe': _media_block,
    'video': _media_block,
    'hr': lambda node, save_image: None,  # paragraphs are already apart
}


def to_body(nodes, save_image):
    """The node tree → body text. `save_image(url) -> str | None` stores a
    picture and returns its URL on our server."""
    blocks = []
    inline = []

    def flush():
        text = re.sub(r'\s+', ' ', ''.join(inline)).strip()
        if text:
            blocks.append(text)
        inline.clear()

    for node in nodes or []:
        convert = None if isinstance(node, str) else BLOCKS.get(node['tag'])
        if convert is None:
            inline.append(node if isinstance(node, str) else _text([node]))
            continue
        flush()
        block = convert(node, save_image)
        if block:
            blocks.append(block)
    flush()
    return '\n\n'.join(blocks)


def image_saver(folder):
    """Downloads pictures into MEDIA/<folder>/ and returns their URLs."""
    counter = {'n': 0}

    def save(url):
        try:
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
        except requests.RequestException:
            return None
        content_type = response.headers.get('Content-Type', '').split(';')[0]
        ext = IMAGE_TYPES.get(content_type) or os.path.splitext(
            urlparse(url).path)[1].lower()
        too_big = len(response.content) > MAX_IMAGE_BYTES
        if ext not in IMAGE_TYPES.values() or too_big:
            return None
        counter['n'] += 1
        name = default_storage.save(f'{folder}/{counter["n"]}{ext}',
                                    ContentFile(response.content))
        return default_storage.url(name)

    return save
