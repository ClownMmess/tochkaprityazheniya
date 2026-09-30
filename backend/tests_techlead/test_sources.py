from datetime import datetime,timezone
from pathlib import Path
from app.integrations.sources.venues import parse_base,parse_krop,parse_stadium
from app.integrations.sources.standup import parse_standup
NOW=datetime(2026,9,29,tzinfo=timezone.utc)
FIXTURES=Path(__file__).resolve().parents[1]/'tests/fixtures'
def test_official_artist_dates_and_unknown_prices():
    base=parse_base((FIXTURES/'base.html').read_text(),NOW)
    artist=next(x for x in base if x['title']=='madk1d')
    assert artist['dates'][0]['start']==1792767600 and artist['price'] is None
    krop=parse_krop((FIXTURES/'krop.html').read_text(),NOW)[0]
    assert krop['title']=='BOULEVARD DEPO' and krop['dates'][0]['start']==1794157200 and krop['price']=='от 3000 рублей'
    stadium=parse_stadium((FIXTURES/'stadium.html').read_text(),NOW)[0]
    assert stadium['title']=='Boulevard Depo' and stadium['dates'][0]['start']==1797094800 and stadium['price'] is None

def test_standup_sessions_grouped_and_music_not_called_comedy():
    rows=parse_standup((FIXTURES/'standup.html').read_text(),NOW)
    show=next(x for x in rows if x['title']=='СУПЕРпроверка комиков с ТВ')
    assert len(show['dates'])>1 and show['categories']==['stand-up']
    assert all(d['price'].startswith('от ') for d in show['dates'])
    assert all(x['categories']==['concert'] for x in rows if 'Atomic Cellos' in x['title'])
