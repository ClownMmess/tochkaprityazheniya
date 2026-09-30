"""Public search endpoint used by KASSIR.RU's own catalogue; no credentials."""
import hashlib
import time
import re
from zoneinfo import ZoneInfo
from urllib.parse import urlparse
import httpx
from app.integrations.sources.common import horizon, iso, price_text
from app.services.locations import city_scope,city_from_name,venue_city

ENDPOINT = 'https://api.kassir.ru/api/search'
DOMAINS = {'msk': 'msk.kassir.ru', 'krd': 'krd.kassir.ru'}
CATEGORY_MAP = {'koncert': 'concert', 'teatr': 'theater', 'shou': 'entertainment',
                'sport': 'sport', 'detyam': 'kids', 'vystavki': 'exhibition',
                'ekskursii': 'tour', 'muzei': 'museum', 'cirk': 'circus',
                'festival': 'festival', 'standup': 'stand-up', 'kino': 'cinema'}
CATEGORY_MAP.update({'muzey':'museum','film':'cinema','obrazovanie':'education',
                     'festivali':'festival','tourist':'tour','prazdniki':'holiday'})


def parse_items(items, city, now, genres=(), include_nearby=False):
    rows = []
    for entry in items:
        if entry.get('type') not in {'event', 'activity'}:
            continue
        event = entry['object']
        venues = [event['venue']] if event.get('venue') else event.get('venues', [])
        # A regional ticket domain includes surrounding cities. Keep the selected city.
        venues = [v for v in venues if venue_city((v.get('address') or {}).get('addressString'),city_from_name((v.get('address') or {}).get('city',''))) in city_scope(city,include_nearby)]
        if not venues:
            continue
        dates = event.get('dateRange') or {}
        # KASSIR public listings display the calendar clock carried in their ISO strings.
        # This is verified against the matching BASE event (10 Oct 2026, 17:00 Moscow).
        # The API serializes this local clock with +00:00; applying UTC adds three hours.
        def local_clock(value):
            parsed=iso(value)
            return parsed.replace(tzinfo=ZoneInfo('Europe/Moscow')) if parsed else None
        start, end = local_clock(event.get('beginsAt') or dates.get('beginsAt')), local_clock(event.get('endsAt') or dates.get('endsAt'))
        if not start or (end or start) < now or start > horizon(now):
            continue
        url = event.get('url') or ''
        if not url.startswith('https://') or not urlparse(url).hostname.endswith('.kassir.ru'):
            continue
        category = CATEGORY_MAP.get(event.get('urlSlug', '').split('/')[0], 'entertainment')
        age = (event.get('ageGroup') or next(iter(event.get('ageGroups', [])), {})).get('name')
        fees = event.get('priceRange') or {}
        for venue in venues:
            row_city=venue_city(venue['address'].get('addressString'),city_from_name(venue['address']['city']))
            place_url = venue.get('url')
            # One card per named production and venue; its dated sessions stay selectable.
            normalized_title=re.sub(r'[^\w]+',' ',event['title'].casefold().replace('ё','е')).strip()
            identity = f"{city}/{normalized_title}/{place_url}"
            rows.append({'id': hashlib.sha256(identity.encode()).hexdigest()[:40],
                'title': event['title'], 'site_url': url, 'city': row_city,
                'description': f"{event['title']}. Площадка: {venue['name']}. Актуальные билеты и полное расписание — на странице KASSIR.RU.",
                'categories': [category], 'genres': list(genres), 'age_restriction': age,
                'images': [{'image': event['posterImage']}] if event.get('posterImage') else [],
                'dates': [{'start': int(start.timestamp()), 'end': int(end.timestamp()) if end else None,
                    'schedule_kind': 'period' if event.get('isMultiDay') else 'session', 'source_url':url,
                    'price':price_text(fees.get('min'),fees.get('max')),
                    'is_free':fees.get('min') == fees.get('max') == 0}],
                'price': price_text(fees.get('min'), fees.get('max')), 'is_free': fees.get('min') == fees.get('max') == 0,
                'place': {'id': place_url or venue['name'], 'title': venue['name'],
                          'address': venue['address'].get('addressString'), 'site_url': place_url},
                'source_genres': list(genres)})
    return rows


def merge_row(rows,row):
    previous=rows.get(row['id'])
    if previous:
        row['genres']=sorted(set(previous.get('genres',[]))|set(row.get('genres',[])))
        dates={d['start']:d for d in previous['dates']}
        dates.update({d['start']:d for d in row['dates']})
        row['dates']=sorted(dates.values(),key=lambda d:d['start'])
    rows[row['id']]=row


def fetch_kassir(city, now, max_pages=160, include_nearby=True):
    rows = {}; complete = True
    # Full public catalogue, then source-labelled rap. No artist allowlist.
    with httpx.Client(timeout=40, follow_redirects=True) as client:
        for category, genres in [(None, ()), (3007, ('hip-hop',)), (3002, ('rock',)), (3004, ('jazz',)), (3001, ('classical',)), (3003, ('pop',))]:
            seen_pages = set()
            for page in range(1, max_pages + 1):
                params = {'domain': DOMAINS[city], 'pageSize': 100, 'currentPage': page,
                          'dateFrom': now.strftime('%d.%m.%Y'), 'dateTo': horizon(now).strftime('%d.%m.%Y')}
                if category: params['categoryId'] = category
                response = client.get(ENDPOINT, params=params); response.raise_for_status()
                data = response.json(); entries = data['items']; pagination = data['pagination']
                signature = tuple((v.get('type'), v.get('object', {}).get('id')) for v in entries)
                if signature in seen_pages:
                    complete = False; break
                seen_pages.add(signature)
                for row in parse_items(entries, city, now, genres,include_nearby):
                    merge_row(rows,row)
                if page >= pagination['pagesCount'] or not entries:
                    break
                time.sleep(0.15)
            else:
                complete = False
    if not rows:
        raise ValueError('Empty catalogue or changed source format')
    return list(rows.values()), complete
