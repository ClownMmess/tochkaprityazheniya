import re
from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
import httpx

MSK=ZoneInfo('Europe/Moscow')
MONTHS=['январь','февраль','март','апрель','май','июнь','июль','август','сентябрь','октябрь','ноябрь','декабрь']
SOURCES={'StandUp Cafe':'https://standupcafe.ru/events','BASE':'https://base-club.com/','КРОП Арена':'https://arenahall.info/krd/','VK Stadium':'https://vk-stadium.ru/'}

def text(node):return node.get_text(' ',strip=True) if node else ''
def forthcoming(day,month,hour,minute,now,weekday=None,year=None):
    # Official upcoming listings omit the year. Choose the next calendar occurrence,
    # checking their published weekday. Never infer a price or a sellable ticket.
    year=year or now.astimezone(MSK).year+(month<now.astimezone(MSK).month)
    dt=datetime(year,month,day,hour,minute,tzinfo=MSK)
    if weekday is not None and dt.weekday()!=weekday:return None
    return dt

def item(source,url,title,dt,image,city,venue,address,description='',price=None,age=None):
    return {'id':url.rstrip('/').split('/')[-1], 'site_url':url,'title':title,
      'description':description,'dates':[{'start':int(dt.timestamp())}],
      'images':[{'image':image}] if image else [],'categories':['concert'],
      'price':f'от {price} рублей' if price else None,'is_free':False,
      'age_restriction':age,'place':{'id':source,'title':venue,'address':address,'site_url':SOURCES[source]},
      'source_name':source,'city':city}

def parse_krop(html,now):
    soup=BeautifulSoup(html,'html.parser');rows=[]
    for node in soup.select('.item-box'):
        a=node.select_one('a.item-hover');name=text(node.select_one('h4'));desc=text(node.select_one('.item-box-desc'))
        match=re.search(r'(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})',desc)
        if not(a and name and match):continue
        d,m,y,h,mi=map(int,match.groups());dt=datetime(y,m,d,h,mi,tzinfo=MSK)
        if dt<now:continue
        fee=re.search(r'(\d[\d\s]*)\s*руб',desc[match.end():]);img=node.select_one('img')
        rows.append(item('КРОП Арена',urljoin(SOURCES['КРОП Арена'],a['href']),name,dt,urljoin(SOURCES['КРОП Арена'],img['src']) if img else None,'krd','КРОП Арена','ул. Путевая, 5/1',price=int(re.sub(r'\s','',fee[1])) if fee else None))
    return rows

def parse_base(html,now):
    soup=BeautifulSoup(html,'html.parser');rows=[]
    posters={a.get('href'):a.img.get('src') for a in soup.select('.posters__item a') if a.img}
    for node in soup.select('.events__item'):
        a=node.select_one('.events__title a');month=node.find_previous(class_='events__month')
        day=text(node.select_one('.events__day'));clock=text(node.select_one('.events__day-time'))
        mt=text(month).lower();match=re.search(r'(пн|вт|ср|чт|пт|сб|вс).*?(\d{1,2}):(\d{2})',clock)
        if not a or mt not in MONTHS or not day.isdigit() or not match:continue
        dt=forthcoming(int(day),MONTHS.index(mt)+1,int(match[2]),int(match[3]),now,['пн','вт','ср','чт','пт','сб','вс'].index(match[1]))
        if not dt or dt<now:continue
        row=item('BASE',a['href'],text(a),dt,posters.get(a['href']),'msk','BASE','ул. Орджоникидзе, 11, стр. 1',text(node.select_one('.events__description')))
        row['date_note']='Год восстановлен из раздела предстоящих событий, месяца и дня недели; дата сверяется при каждом обновлении.'
        rows.append(row)
    return rows

def parse_stadium(html,now):
    soup=BeautifulSoup(html,'html.parser');rows=[]
    for node in soup.select('.js-product'):
        a=node.select_one('a.js-product-link');name=text(node.select_one('.js-product-name'));date=text(node.select_one('.js-product-price'))
        match=re.search(r'(\d{2})\.(\d{2})\s+(ПН|ВТ|СР|ЧТ|ПТ|СБ|ВС)\s+(\d{1,2}):(\d{2})',date)
        if not(a and name and match):continue
        explicit=re.search(r'20\d{2}',a.get('href',''));year=int(explicit[0]) if explicit else None
        dt=forthcoming(int(match[1]),int(match[2]),int(match[4]),int(match[5]),now,['ПН','ВТ','СР','ЧТ','ПТ','СБ','ВС'].index(match[3]),year)
        if not dt or dt<now:continue
        img=node.select_one('.js-product-img');age=text(node.select_one('.t776__mark'))
        row=item('VK Stadium',urljoin(SOURCES['VK Stadium'],a['href']),name,dt,img.get('data-original') if img else None,'msk','VK Stadium','Ленинградский проспект, 80, корп. 17',age=age if re.fullmatch(r'\d+\+',age) else None)
        row['date_note']='Год из адреса события либо ближайшего года предстоящей афиши; день недели проверен.'
        rows.append(row)
    return rows

def fetch_venue(source,now):
    from app.integrations.sources.standup import parse_standup
    parser={'StandUp Cafe':parse_standup,'BASE':parse_base,'КРОП Арена':parse_krop,'VK Stadium':parse_stadium}[source]
    with httpx.Client(timeout=40,follow_redirects=True) as client:
        response=client.get(SOURCES[source]);response.raise_for_status();rows=parser(response.text,now)
        if not rows:raise ValueError('Source markup changed or upcoming listing is empty')
        # Detail-page images for events without a poster in the listing.
        if source=='BASE':
            for row in rows:
                if row['images']:continue
                try:
                    r=client.get(row['site_url']);r.raise_for_status();s=BeautifulSoup(r.text,'html.parser')
                    image=s.select_one('meta[property="og:image"]')
                    photo=s.select_one('img[src*="base-club.com/uploads/"]')
                    url=image.get('content') if image else photo.get('src') if photo else None
                    if url:row['images']=[{'image':url}]
                except (httpx.HTTPError,ValueError):pass
    return rows
