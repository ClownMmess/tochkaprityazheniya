"""Documented public API: https://dev.timepad.ru/api/get-v1-events/ ."""
from datetime import datetime
import httpx

def fetch_timepad(city,now,token=None):
    headers={'Authorization':'Bearer '+token} if token else {}
    rows=[];complete=False
    with httpx.Client(timeout=30,headers=headers) as client:
        for skip in range(0,10000,100):
            r=client.get('https://api.timepad.ru/v1/events/',params={'cities':'Москва' if city=='msk' else 'Краснодар','starts_at_min':now.isoformat(),'limit':100,'skip':skip,'fields':'description_short,poster_image,location,organization,ticket_types,age_limit','sort':'+starts_at'})
            r.raise_for_status();data=r.json()
            for value in data.get('values',[]):
                tickets=[t for t in value.get('ticket_types',[]) if t.get('is_active') and not t.get('is_promocode_locked') and isinstance(t.get('price'),(int,float))]
                amounts=[int(t['price']) for t in tickets];free=bool(amounts) and all(x==0 for x in amounts)
                low=min(amounts) if amounts else None;price='Бесплатно' if free else f'от {low} рублей' if low is not None else None
                org=value.get('organization') or {};location=value.get('location') or {};poster=value.get('poster_image') or {}
                try:
                    start=datetime.fromisoformat(value['starts_at']).timestamp();end=datetime.fromisoformat(value['ends_at']).timestamp() if value.get('ends_at') else None
                except (ValueError,KeyError):continue
                rows.append({'id':value['id'],'title':value['name'],'site_url':value['url'],'description':value.get('description_short',''),'dates':[{'start':start,'end':end}], 'price':price,'is_free':free,'age_restriction':value.get('age_limit'),'categories':[], 'images':[{'image':poster.get('default_url')}], 'place':{'id':org.get('id'),'title':org.get('name'),'site_url':org.get('url'),'address':location.get('address')},'city':city,'source_name':'Timepad'})
            if skip+100>=data.get('total',0):complete=True;break
    return rows,complete
