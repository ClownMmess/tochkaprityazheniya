"""Offline events published in Nethouse's public city listings."""
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from app.integrations.sources.common import horizon

CITY_IDS = {'msk': 1, 'krd': 16}
CATEGORIES = {3: 'kids', 20: 'theater', 53: 'concert', 14: 'exhibition',
              38: 'exhibition', 11: 'entertainment', 6: 'sport', 56: 'party'}

def parse_page(html, city, now):
    tag = BeautifulSoup(html, 'html.parser').select_one('#__NEXT_DATA__')
    if not tag:
        raise ValueError('Public listing data unavailable')
    data = json.loads(tag.string or tag.get_text())['props']['pageProps']['data']
    groups = data['lists']['collection']
    if not isinstance(groups, list) or not groups:
        raise ValueError('Empty or changed public listing')
    rows = {}
    for group in groups:
        for event in group['events']:
            if event['city_id'] != CITY_IDS[city] or event.get('is_online') or event.get('is_course'):
                continue
            if event['name'].lower().startswith('материалы конференции'):
                continue
            start, end = event.get('date_start'), event.get('date_end')
            undated = bool(event.get('is_dateless'))
            if (end or start or 0) < now.timestamp():
                continue
            if not undated and (not start or start > horizon(now).timestamp()):
                continue
            url = event.get('url', '')
            if urlparse(url).scheme != 'https' or not urlparse(url).hostname:
                continue
            image = event.get('image') or ''
            if image.startswith('https://events.nethouse.ruhttps://'):
                image = image[len('https://events.nethouse.ru'):]
            address = event.get('address') or ''
            rows[event['id']] = {
                'id': str(event['id']), 'city': city, 'kind': 'place' if undated else 'event',
                'title': event['name'], 'site_url': url,
                'description': event['name'] + '. ' + address + '. Регистрация и условия участия — на странице организатора.',
                'categories': [CATEGORIES.get(event.get('category_id'), 'education')],
                'dates': [] if undated else [{'start': start, 'end': end}],
                'schedule_note': 'Постоянная программа в каталоге Nethouse. Дату посещения согласуйте с организатором.' if undated else None,
                'price': event.get('price'), 'is_free': event.get('is_free') == 1,
                'images': [{'image': image}] if image else [],
                'place': {'id': address or str(event['id']), 'title': address or 'Место уточняется', 'address': address, 'site_url': url},
            }
    return list(rows.values()), True


def fetch_nethouse(city, now):
    with httpx.Client(timeout=35, follow_redirects=True) as client:
        response = client.get('https://afisha.nethouse.ru/' + city)
        response.raise_for_status()
    return parse_page(response.text, city, now)
