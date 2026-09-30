"""Public venue pages and a fair directory; undated places never become fake sessions."""
import json,re,hashlib
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import httpx
from app.integrations.sources.common import iso,horizon

LOCAL_SOURCES={
 'Loft to Play Играй':('https://loft-to-play-igrai.ru/','krd'),
 'GeekTime':('https://www.geek-time.ru/','msk'),
 'Соколиная нора':('https://sokolinayanora.ru/','msk'),
 'В мире цветов':('https://vistavka-cvetov-krasnodar.ru/','krd'),
 'Дуняша Маркет':('https://dunyashamarket.ru/','msk'),
 'SunFair — справочник ярмарок':('https://sunfair.ru/fair','msk'),
 'Краснодарская ярмарка':('https://xn--80aamwbi1acd6l.xn--p1ai/','krd'),
}

def soup_text(raw):
    soup=BeautifulSoup(raw,'html.parser')
    for tag in soup(['script','style']):tag.decompose()
    return soup,soup.get_text(' ',strip=True).replace('\x00','')

def parse_anticafe(source,raw):
    url,city=LOCAL_SOURCES[source];soup,text=soup_text(raw)
    if 'антикафе' not in text.casefold():raise ValueError('Venue description unavailable')
    if source=='Loft to Play Играй':
        match=re.search(r'г\.\s*Краснодар,\s*(ул\.\s*[^@]+?)\s+admin@',text)
        address=match[1] if match else None
        price=re.search(r'Стоимость посещени\w* в общем зале:\s*(\d+)\s*руб\.\s*в час',text)
        fee=f'{price[1]} ₽ в час на человека' if price else None
        schedule='Часы работы и бронирование уточняйте у площадки.'
    elif source=='GeekTime':
        match=re.search(r'Новослободская ул[.,\s]+(?:д[.,\s]*)?36/1[сc]1',text,re.I)
        address=match[0] if match else None;fee=None
        schedule='Круглосуточно' if 'круглосуточно' in text.lower() else 'Режим работы уточняйте у площадки.'
    else:
        match=re.search(r'Щербаковская ул\.,\s*53к2',text)
        address=match[0] if match else None;fee=None;schedule='Режим работы уточняйте у площадки.'
    if not address:raise ValueError('Verified venue address not found')
    poster=soup.select_one('meta[property="og:image"]');image=poster.get('content') if poster else None
    if source=='Loft to Play Играй':
        candidates=[img.get('src') for img in soup.select('img[src]') if '/wp-content/uploads/' in img['src'] and not re.search(r'лого|logo|icon',img['src'],re.I)]
        if candidates:image=urljoin(url,candidates[0])
    return [{'id':'main','city':city,'title':'Антикафе '+source,'kind':'place','categories':['anticafe'],
        'genres':['anticafe','board-games'],'site_url':url,'dates':[],'schedule_note':schedule,'price':fee,
        'description':'Место для встреч и настольных игр. Условия посещения, тарифы и бронирование — на сайте площадки.',
        'place':{'id':source,'title':source,'address':address,'site_url':url},
        'images':[{'image':image}] if image else []}]

def parse_flowers(raw,now):
    soup=BeautifulSoup(raw,'html.parser');rows=[]
    for tag in soup.select('script[type="application/ld+json"]'):
        data=json.loads(tag.get_text())
        if data.get('@type')!='Event':continue
        start,end=iso(data.get('startDate')),iso(data.get('endDate'))
        if not start or (end or start)<now or start>horizon(now):continue
        place=data['location'];url=data['url'];image=data.get('image') or []
        rows.append({'id':data.get('@id',url)+'/'+start.date().isoformat(),'city':'krd','title':data['name'],'categories':['fair'],
          'description':'Выставка-продажа комнатных и садовых растений от цветоводов. Подробности — на сайте организатора.',
          'site_url':url,'dates':[{'start':int(start.timestamp()),'end':int(end.timestamp()),'schedule_kind':'period'}],
          'is_free':data.get('isAccessibleForFree') is True,
          'place':{'id':place.get('@id',place['name']),'title':place['name'],'address':place['address']['streetAddress'],'site_url':url},
          'images':[{'image':image[0]}] if image else []})
    return rows

def parse_dunyasha(raw,now):
    from datetime import datetime,timedelta
    from zoneinfo import ZoneInfo
    soup,text=soup_text(raw);url=LOCAL_SOURCES['Дуняша Маркет'][0]
    months={'января':1,'февраля':2,'марта':3,'апреля':4,'мая':5,'июня':6,'июля':7,'августа':8,'сентября':9,'октября':10,'ноября':11,'декабря':12}
    match=re.search(r'((?:\d{1,2}[-–,\sи]+)+\d{1,2})\s+('+'|'.join(months)+r')\s+(20\d{2})',text,re.I)
    hours=re.search(r'с\s*(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})',text,re.I)
    address=re.search(r'по адресу:\s*(.+?)\s+с\s*\d{1,2}:',text,re.I)
    if not match or not hours or not address:raise ValueError('Market dates or address changed')
    # This organizer enumerates days (8-9-10-11 и 14-15-16-17-18); no dates filled into gaps.
    days=[int(v) for v in re.findall(r'\d+',match[1])];dates=[]
    for day in days:
        start=datetime(int(match[3]),months[match[2].lower()],day,int(hours[1]),int(hours[2]),tzinfo=ZoneInfo('Europe/Moscow'))
        end=start.replace(hour=int(hours[3]),minute=int(hours[4]))
        if end>=now and start<=horizon(now):dates.append({'start':int(start.timestamp()),'end':int(end.timestamp())})
    if not dates:return []
    poster=soup.select_one('meta[property="og:image"]')
    return [{'id':'market/'+match[3]+'/'+str(months[match[2].lower()]),'city':'msk','title':'Ярмарка российских дизайнеров «Дуняша Маркет»',
      'site_url':url,'categories':['fair'],'dates':dates,'is_free':'ВХОД СВОБОДНЫЙ' in text.upper(),
      'description':'Маркет одежды, аксессуаров и изделий ручной работы. Даты и программа опубликованы организатором.',
      'place':{'id':'artplay','title':'Центр дизайна ARTPLAY','address':address[1].strip(),'site_url':url},
      'images':[{'image':poster['content']}] if poster else []}]

def parse_fair_directory(raw):
    soup,_=soup_text(raw);rows=[]
    for block in soup.select('.card-block'):
        title=block.select_one('h4 a[href]');addr=block.select_one('[itemprop="address"]')
        if not title or not addr:continue
        text=block.get_text(' ',strip=True)
        if re.search(r'не работает|закрыт',text,re.I):continue
        hours=re.search(r'Режим работы(?: ярмарки)?:\s*(.+?)(?:Количество|Единый|Электронная|$)',text,re.I)
        url=urljoin('https://sunfair.ru',title['href']);name=title.get_text(' ',strip=True)
        rows.append({'id':title['href'],'city':'msk','title':name,'kind':'place','site_url':url,'categories':['fair'],'dates':[],
          'schedule_note':(hours[1].strip() if hours else 'Дни работы уточняйте у организатора.')+' Перед поездкой проверьте работу площадки по ссылке.',
          'description':'Ярмарочная площадка из справочника SunFair. Это место с режимом работы, без отдельного датированного сеанса.',
          'place':{'id':title['href'],'title':name,'address':addr.get_text(' ',strip=True),'site_url':url}})
    if not rows:raise ValueError('Fair directory unavailable')
    return rows

def parse_krasnodar_fairs(raw):
    soup,text=soup_text(raw);rows={};base=LOCAL_SOURCES['Краснодарская ярмарка'][0]
    if not re.search(r'Каждую субботу.+?ярмарки выходного дня',text,re.I):
        raise ValueError('Municipal fair schedule unavailable')
    for link in soup.select('a[href]'):
        name=link.get_text(' ',strip=True)
        if not name.startswith('Ярмарка по адресу:'):continue
        address=name.split(':',1)[1].strip();url=urljoin(base,link['href'])
        if not url.startswith(base) or not re.search(r'\d',address):continue
        rows[url]={'id':hashlib.sha256(url.encode()).hexdigest(),'city':'krd','title':'Ярмарка выходного дня — '+address,'kind':'place','site_url':url,'categories':['fair'],'dates':[],
          'schedule_note':'По субботам. Часы работы и возможные изменения уточняйте у организатора перед поездкой.',
          'description':'Муниципальная ярмарка местных продуктов. Адрес и еженедельный график опубликованы МБУ «Краснодарская ярмарка».',
          'place':{'id':url,'title':'Ярмарка выходного дня','address':address,'site_url':url}}
    if not rows:raise ValueError('Municipal fair addresses unavailable')
    return list(rows.values())

def fetch_local(source,now):
    url,_=LOCAL_SOURCES[source]
    with httpx.Client(timeout=25,follow_redirects=True) as client:
        if source=='SunFair — справочник ярмарок':
            rows={};page=1
            while page<=20:
                response=client.get(url,params={'page':page});response.raise_for_status()
                for row in parse_fair_directory(response.text):rows[row['id']]=row
                soup=BeautifulSoup(response.text,'html.parser')
                pages=[int(m[1]) for a in soup.select('a[href]') if (m:=re.search(r'/fair\?page=(\d+)',a['href']))]
                if not pages or page>=max(pages):return list(rows.values()),True
                page+=1
            return list(rows.values()),False
        response=client.get(url);response.raise_for_status()
    rows=parse_flowers(response.text,now) if source=='В мире цветов' else parse_dunyasha(response.text,now) if source=='Дуняша Маркет' else parse_krasnodar_fairs(response.text) if source=='Краснодарская ярмарка' else parse_anticafe(source,response.text)
    return rows,False
