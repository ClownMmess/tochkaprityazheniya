"""Museums, parks and sights from KudaGo's separate, public places catalogue."""
import httpx

PLACE_CATEGORIES = {'anticafe':'anticafe', 'museums': 'museum', 'art-centers': 'exhibition', 'art-space': 'exhibition',
                    'park': 'park', 'amusement': 'amusement', 'attractions': 'landmark',
                    'homesteads': 'landmark', 'palace': 'landmark', 'prirodnyj-zapovednik': 'park'}

def fetch_places(base, city):
    rows = []; complete = False
    params = {'lang': 'ru', 'location': city, 'page_size': 100,
              'categories': ','.join(PLACE_CATEGORIES), 'text_format': 'text',
              'fields': 'id,title,address,site_url,images,categories,timetable,is_closed,description'}
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for page in range(1, 80):
            r = client.get(base.rstrip('/') + '/places/', params={**params, 'page': page}); r.raise_for_status()
            data = r.json()
            for place in data['results']:
                if place.get('is_closed'): continue
                category = next((PLACE_CATEGORIES[c] for c in PLACE_CATEGORIES if c in place.get('categories', [])), None)
                if not category: continue
                rows.append({'id': 'place-' + str(place['id']), 'kind': 'place', 'city': city,
                    'title': place['title'], 'site_url': place['site_url'], 'images': place.get('images', []),
                    'categories': [category], 'dates': [], 'is_free': False,
                    'description': f"{place['title']}. Адрес: {place.get('address', '')}. Режим работы и стоимость посещения уточняйте на странице источника.",
                    'schedule_note': place.get('timetable') or 'Режим работы уточняйте у площадки.',
                    'place': {'id': place['id'], 'title': place['title'], 'address': place.get('address'), 'site_url': place['site_url']}})
            if not data.get('next'): complete = True; break
    return rows, complete
