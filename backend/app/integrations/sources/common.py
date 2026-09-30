"""Read public catalogue data, never execute scripts supplied by a source."""
import calendar
import json
from datetime import datetime
from bs4 import BeautifulSoup


def horizon(now, months=6):
    index = now.month - 1 + months
    year, month = now.year + index // 12, index % 12 + 1
    return now.replace(year=year, month=month, day=min(now.day, calendar.monthrange(year, month)[1]))


def nuxt_data(html):
    tag = BeautifulSoup(html, 'html.parser').select_one('#__NUXT_DATA__')
    if not tag:
        raise ValueError('Missing public catalogue data')
    values = json.loads(tag.string or tag.get_text())
    cache = {}

    def decode(index):
        if index < 0:
            return None
        if index in cache:
            return cache[index]
        value = values[index]
        if isinstance(value, dict):
            result = {}; cache[index] = result
            result.update({key: decode(ref) for key, ref in value.items()})
        elif isinstance(value, list):
            if value and isinstance(value[0], str):
                result = decode(value[1]) if len(value) > 1 and isinstance(value[1], int) else None
            else:
                result = []; cache[index] = result
                result.extend(decode(ref) for ref in value)
        else:
            result = value
        cache[index] = result
        return result
    return decode(0)


def iso(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None


def price_text(low, high):
    if low is None:
        return None
    if high is not None:
        return f'{int(low)}–{int(high)} рублей' if high != low else f'{int(low)} рублей'
    return f'от {int(low)} рублей'
