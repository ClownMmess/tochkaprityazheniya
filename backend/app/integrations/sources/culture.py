"""Public structured pages of VDNH and Garage. Undated places stay undated."""
import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin
import re
import httpx
from bs4 import BeautifulSoup
import json
from app.integrations.sources.common import nuxt_data, iso, horizon, price_text

def classify(title, fallback='exhibition'):
    t = title.casefold()
    for pattern, slug in [(r'экскурси|прогулк', 'tour'), (r'мастер.класс|лекци|обучен', 'education'),
                          (r'ярмарк|маркет', 'fair'), (r'концерт', 'concert'), (r'спектакл', 'theater'),
                          (r'аттракцион|колесо обозрения', 'amusement'), (r'выставк|экспозиц', 'exhibition'),
                          (r'музе[йяею]', 'museum'), (r'парк|сад', 'park')]:
        if re.search(pattern, t): return slug
    return fallback


def parse_vdnh(html, now):
    data = nuxt_data(html)['data']
    page = next(v for k, v in data.items() if k.startswith('page/'))
    events = page['config']['events']; rows = []
    for event in events:
        title = event['name']; types = ' '.join(v['name'] for v in event.get('eventTypes', []))
        if re.search(r'консьерж|бюро находок|камера хранения|центр развития карьеры|аренда|прокат|парковк', title, re.I):
            continue
        schedule = event.get('schedule') or {}
        start, end = iso(schedule.get('action_start_date')), iso(schedule.get('action_end_date'))
        if (end and end < now) or (start and start > horizon(now)): continue
        # No ending date is an ongoing place/programme, not an invented future show.
        kind = 'event' if start and end else 'place'
        category = classify(title, classify(types, 'entertainment'))
        if category == 'exhibition' and kind == 'place' and 'музе' in title.casefold(): category = 'museum'
        rows.append({'id': str(event['id']), 'title': title,
            'site_url': event.get('link') or urljoin('https://vdnh.ru/', event['url'] + '/'),
            'city': 'msk', 'kind': kind, 'categories': [category],
            'description': f'{title}. ВДНХ. Часы работы, условия посещения и полное расписание — на официальной странице.',
            'schedule_note': 'Период проведения; дни и часы посещения уточняйте у ВДНХ.' if kind == 'event' else 'Постоянная площадка или программа. Режим работы — на официальной странице.',
            'dates': [{'start': int(start.timestamp()), 'end': int(end.timestamp()), 'schedule_kind': 'period'}] if kind == 'event' else [],
            'images': [{'image': event['image']}] if event.get('image') else [],
            'is_free': any(v.get('name') == 'Бесплатно' for v in event.get('badges', [])),
            'place': {'id': 'vdnh', 'title': 'ВДНХ', 'address': 'Москва, проспект Мира, 119', 'site_url': 'https://vdnh.ru/'}})
    if not rows: raise ValueError('Changed VDNH catalogue format')
    return rows


def parse_garage(html, now):
    tag = BeautifulSoup(html, 'html.parser').select_one('#__NEXT_DATA__')
    data = json.loads(tag.string)['props']['pageProps']['initialState']['calendarEvents']['timeRanges']
    rows = []
    for event in data['events'].values():
        a = event['attributes']; related = event['relationships']
        ranges = [v for v in data['timeRanges'].values() if (v['relationships'].get('event', {}).get('data') or {}).get('id') == event['id']]
        # Parent cards without their own published sessions are not duplicated.
        if not ranges: continue
        dates = []
        for r in ranges:
            v = r['attributes']; loc_id = (r['relationships'].get('location', {}).get('data') or {}).get('id')
            loc = data['locations'].get(loc_id, {}).get('attributes', {}).get('title', '')
            if 'Онлайн' in loc or 'Петербург' in loc: continue
            start, end = v.get('startsAt'), v.get('endsAt')
            if not start or (end or start) < now.timestamp() or start > horizon(now).timestamp(): continue
            dates.append({'start': start, 'end': end, 'schedule_kind': 'period' if v.get('wholeDay') else 'session',
                          'price': price_text(v.get('minPrice'), v.get('maxPrice')), 'is_free': v.get('free') or v.get('freeByRegistration')})
        if not dates: continue
        image = (a.get('coverImage') or a.get('previewImage') or {}).get('url')
        kind_id = (related.get('kind', {}).get('data') or {}).get('id')
        kind = data.get('filterValues', {}).get(kind_id, {}).get('attributes', {}).get('title', '')
        rows.append({'id': event['id'], 'title': a['title'], 'city': 'msk',
            'site_url': 'https://garagemca.org/ru/event/' + a['slug'],
            'categories': [classify(a['title'] + ' ' + kind)], 'dates': dates,
            'description': f"{a['title']}. Музей «Гараж». {kind}. Подробности и регистрация — на официальной странице.",
            'age_restriction': a.get('ageRestriction'), 'images': [{'image': image}] if image else [],
            'price': price_text(a.get('minPrice'), a.get('maxPrice')), 'is_free': a.get('free') or a.get('freeByRegistration'),
            'place': {'id': 'garage', 'title': 'Музей «Гараж»', 'address': 'Москва, Крымский Вал, 9, стр. 32', 'site_url': 'https://garagemca.org/'}})
    if not rows: raise ValueError('Empty Garage timetable or changed markup')
    return rows


def fetch_culture(source, now):
    url, parser = {'ВДНХ': ('https://vdnh.ru/events/', parse_vdnh),
                   'Музей «Гараж»': ('https://garagemca.org/ru/events', parse_garage)}[source]
    with httpx.Client(timeout=40, follow_redirects=True) as client:
        response = client.get(url); response.raise_for_status()
        return parser(response.text, now), False  # Daily page is not an exhaustive cancellation feed.
