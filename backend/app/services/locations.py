"""Supported catalogue areas. Nearby means this named urban area, not a GPS radius."""
from typing import Literal
import re

CITIES = {
    'msk': ('Москва', 'msk'), 'krd': ('Краснодар', 'krd'),
    'khimki': ('Химки', 'msk'), 'mytishchi': ('Мытищи', 'msk'),
    'korolev': ('Королёв', 'msk'), 'krasnogorsk': ('Красногорск', 'msk'),
    'odintsovo': ('Одинцово', 'msk'), 'balashikha': ('Балашиха', 'msk'),
    'lyubertsy': ('Люберцы', 'msk'), 'reutov': ('Реутов', 'msk'),
    'dolgoprudny': ('Долгопрудный', 'msk'), 'vidnoe': ('Видное', 'msk'),
    'podolsk': ('Подольск', 'msk'), 'shchelkovo': ('Щёлково', 'msk'),
    'dinskaya': ('Динская', 'krd'), 'yablonovsky': ('Яблоновский', 'krd'),
    'enem': ('Энем', 'krd'), 'adygeysk': ('Адыгейск', 'krd'),
    'goryachy-klyuch': ('Горячий Ключ', 'krd'), 'afipsky': ('Афипский', 'krd'),
    'novotitarovskaya': ('Новотитаровская', 'krd'),
    'novaya-adygeya': ('Новая Адыгея', 'krd'),
}
CityCode = Literal[tuple(CITIES)]
CITY_PATTERN = '^(' + '|'.join(CITIES) + ')$'

def city_scope(city, include_nearby=False):
    if not city: return []
    if not include_nearby: return [city]
    region=CITIES[city][1]
    return [slug for slug,(_,area) in CITIES.items() if area==region]

def city_from_name(name):
    value=(name or '').casefold().replace('ё','е').strip()
    for prefix in ['г. ', 'город ', 'станица ', 'ст-ца ', 'посёлок ', 'поселок ', 'пгт ', 'п. ']:
        if value.startswith(prefix): value=value[len(prefix):]
    return next((slug for slug,(label,_) in CITIES.items() if label.casefold().replace('ё','е')==value),None)

def venue_city(address, fallback):
    """Ticket-domain 'city' is regional: the physical address has priority."""
    text=(address or '').casefold().replace('ё','е')
    for slug,(label,_) in CITIES.items():
        if re.search(r'\b'+re.escape(label.casefold().replace('ё','е'))+r'\b',text):return slug
    if re.search(r'\bг(?:ород)?\.?\s*[а-я]|\bст(?:аница|-ца|\.)\s*[а-я]|\bпгт\b|\bс\.\s*[а-я]|\bпос[её]лок\b|\bобл\.|\bр-н\b|\bкрай\b|\bреспублика\b',text):return None
    return fallback

CITY_WORDS = {'msk':r'москв[аеуы]?\b','krd':r'краснодар(?:е|а|у)?\b',
    **{slug:label.casefold().replace('ё','е')[:-1] if label.endswith(('ы','о','я','й')) else label.casefold().replace('ё','е') for slug,(label,_) in CITIES.items() if slug not in {'msk','krd'}}}
