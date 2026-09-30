"""Price normalization shared by import and budget filters."""
import re
import html


def normalize_price(raw, declared_free=False):
    text = html.unescape(re.sub(r'<[^>]+>', ' ', str(raw or ''))).lower()
    text = re.sub(r'\s+', ' ', text.replace('\xa0', ' ').replace('\u202f', ' ')).strip(' .!')
    number = r'(\d+(?: \d{3})*)'
    currency = r'(?:₽|руб(?:\.|лей|ля|ль)?|р\.)?'
    exact = re.fullmatch(number + r'\s*' + currency, text)
    interval = re.fullmatch(r'(?:от\s*)?' + number + r'\s*(?:₽|руб\.?|рублей)?\s*(?:–|—|-|до)\s*' + number + r'\s*' + currency, text)
    lower = re.fullmatch(r'от\s*' + number + r'\s*' + currency, text)
    if interval:
        low, high = [int(interval[i].replace(' ', '')) for i in (1, 2)]
        return (low, high, high == 0) if low <= high else (None, None, False)
    if exact:
        value = int(exact[1].replace(' ', ''))
        return value, value, value == 0
    if lower:
        return int(lower[1].replace(' ', '')), None, False
    listed = re.match(r'^(от\s*)?' + number + r'\s*(?:₽|руб(?:\.|лей|ля|ль)?)(?=\s|[,;(]|$)', text)
    if listed:
        # Only an explicit leading ticket price; group tariffs and deposits stay unknown.
        tail = text[listed.end():]
        if not re.search(r'за команд|за групп|депозит|в час|за час|за минут', tail):
            value = int(listed[2].replace(' ', ''))
            if value > 0:
                return value, None, False
    # A free-entry flag must not override an explicit paid price or a conditional discount.
    positive = any(int(n.replace(' ', '')) > 0 for n in re.findall(number + r'\s*(?:₽|руб|р\.)', text))
    conditional = bool(re.search(r'льгот|пенсионер|детям|инвалид|при\s|до\s*\d', text))
    free_text = bool(re.fullmatch(r'(?:бесплатно|вход (?:свободный|свободен|бесплатный|бесплатен))(?:[,;: ]+(?:по регистрации|необходима регистрация|нужна регистрация|регистрация обязательна))?', text))
    free = not positive and not conditional and (free_text or bool(declared_free))
    return (0, 0, True) if free else (None, None, False)


def repair_cached_prices(session):
    from sqlalchemy import select
    from app.models import Occurrence
    for occurrence in session.scalars(select(Occurrence)):
        low, high, free = normalize_price(occurrence.price_text, occurrence.is_free)
        occurrence.price_min, occurrence.price_max, occurrence.is_free = low, high, free
