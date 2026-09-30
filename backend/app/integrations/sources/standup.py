"""Public official programme; grouped recurring formats retain per-session prices."""
import re,hashlib
from datetime import datetime
from bs4 import BeautifulSoup
from app.integrations.sources.venues import text,MSK
URL='https://standupcafe.ru/events'
MONTHS=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря']

def parse_standup(html,now):
    soup=BeautifulSoup(html,'html.parser');groups={}
    for node in soup.select('.card'):
        link=node.select_one('a.link-to-event');image=node.select_one('img.event-image-card')
        labels=node.select('.text-date-time-bg-color-mode');name=text(node.select_one('.text-color-mode .position-absolute'))
        if not (link and name and len(labels)==2):continue
        match=re.fullmatch(r'(\d{1,2})\s+('+('|'.join(MONTHS))+')',text(labels[0]));clock=re.fullmatch(r'(\d{1,2}):(\d{2})',text(labels[1]))
        fee=re.search(r'ОТ\s+(\d[\d\s]*)\s*₽',text(link))
        if not(match and clock and fee):continue
        month=MONTHS.index(match[2])+1;year=now.astimezone(MSK).year+(month<now.astimezone(MSK).month)
        start=datetime(year,month,int(match[1]),int(clock[1]),int(clock[2]),tzinfo=MSK)
        if start<now:continue
        title=name;category='concert' if re.search(r'Atomic Cellos|рок-хиты',name,re.I) and 'стендап' not in name.lower() else 'stand-up'
        key=hashlib.sha256(name.casefold().encode()).hexdigest()[:24];fee=int(re.sub(r'\s','',fee[1]))
        row=groups.setdefault(key,{'id':key,'site_url':URL,'title':title,'description':'Программа площадки StandUp Cafe. Выберите дату в афише источника.','dates':[],'images':[{'image':image['src']}] if image else [],'categories':[category],'price':None,'is_free':False,'age_restriction':None,'place':{'id':'standup-cafe','title':'StandUp Cafe','site_url':'https://standupcafe.ru/'},'city':'msk','source_name':'StandUp Cafe','date_note':'Год ближайшего предстоящего календарного события; источник публикует месяц и число.'})
        row['dates'].append({'start':int(start.timestamp()),'price':f'от {fee} рублей','is_free':False})
    return list(groups.values())
