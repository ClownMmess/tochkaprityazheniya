from app.services.locations import city_scope
from app.services.matching import interest_match
from datetime import datetime,time,timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select,func,or_,and_,case
import re
from collections import Counter,defaultdict
from app.integrations.llm.fallback import ARTISTS, correct_text
from app.integrations.sources.common import horizon
from fastapi import HTTPException
from app.models import *
from app.db.base import utcnow,aware
MSK=ZoneInfo("Europe/Moscow")

def actual_clause():
    fresh_places=select(Event.id).where(Event.kind=='place',Event.last_seen_at>=utcnow()-timedelta(days=30)).correlate(None)
    return (Occurrence.status=="ACTIVE",Occurrence.source_available.is_(True),or_(func.coalesce(Occurrence.ends_at,Occurrence.starts_at)>=utcnow(),and_(Occurrence.schedule_kind=='place',Occurrence.event_id.in_(fresh_places))))
def is_actual(o):return o.status=="ACTIVE" and o.source_available and (o.schedule_kind=="place" or aware(o.ends_at or o.starts_at)>=utcnow())
def option(s,oid):
    o=s.get(Occurrence,oid)
    if not o:raise HTTPException(404,"event_not_found")
    return o

def warm(s,rows,user_id=None):
    """Keep related objects alive and load links in batches, not once per event card."""
    cache=s.info.setdefault('catalog',{'events':{},'objects':[],'orgs':defaultdict(list),'genres':defaultdict(list),'tracking':{}})
    missing={o.event_id for o in rows if o.event_id not in cache['events']}
    if missing:
        events=list(s.scalars(select(Event).where(Event.id.in_(missing))))
        cache['events'].update({e.id:e for e in events})
        if not cache['objects']:
            for model in (Category,City,EventSource,Interest):cache['objects'].extend(s.scalars(select(model)))
        for eid,org in s.execute(select(EventOrganizer.event_id,Organizer).join(Organizer,Organizer.id==EventOrganizer.organizer_id).where(EventOrganizer.event_id.in_(missing))):cache['orgs'][eid].append(org)
        for eid,genre in s.execute(select(EventInterestCategory.event_id,InterestCategory).join(InterestCategory,InterestCategory.id==EventInterestCategory.category_id).where(EventInterestCategory.event_id.in_(missing))):cache['genres'][eid].append(genre)
    if user_id and user_id not in cache['tracking']:
        cache['tracking'][user_id]={t.occurrence_id:t for t in s.scalars(select(TrackedEvent).where(TrackedEvent.user_id==user_id,TrackedEvent.status=='active'))}
    return cache

def unique_events(s,rows):
    # A ticket session stays addressable for reminders, but catalogue cards represent events.
    counts=Counter(o.event_id for o in rows);s.info['occurrence_counts']=counts
    seen=set();result=[]
    warm(s,rows)
    for row in rows:
        event=s.get(Event,row.event_id)
        normalize=lambda value:re.sub(r'[^\w]+',' ',(value or '').casefold().replace('ё','е')).strip()
        venue_key=re.sub(r"^(?:клуб|club)\s+","",normalize(row.venue))
        key=(normalize(event.title),row.city_id,venue_key)
        if key not in seen:result.append(row);seen.add(key)
    return result

def query_occurrences(s,*,city=None,include_nearby=False,date_from=None,date_to=None,categories=(),price_max=None,age_max=None,age_exact=None,include_unknown_age=False,is_free=False,query=None,time_of_day=None,organizers=(),interest_categories=(),include_demo=False,excluded_categories=(),performers=(),source=None,venue=None,price_match="from",sort="date",venue_type=None,keywords=(),kind=None):
    q=select(Occurrence).join(Event).join(City,City.id==Occurrence.city_id).join(Category,Category.id==Event.category_id).where(*actual_clause())
    q=q.where(Event.is_demo==include_demo)
    if city:q=q.where(City.slug.in_(city_scope(city,include_nearby)))
    if kind:q=q.where(Event.kind==kind)
    # Published horizon: six calendar months, including ongoing periods and undated places.
    q=q.where(or_(Occurrence.schedule_kind=='place',Occurrence.starts_at<=horizon(utcnow())))
    if date_from:q=q.where(or_(Occurrence.schedule_kind=="place",func.coalesce(Occurrence.ends_at,Occurrence.starts_at)>=datetime.combine(date_from,time.min,MSK)))
    if date_to:q=q.where(Occurrence.starts_at<datetime.combine(date_to+timedelta(days=1),time.min,MSK))
    if categories:q=q.where(Category.slug.in_(categories))
    if excluded_categories:q=q.where(Category.slug.notin_(excluded_categories))
    if source:q=q.join(EventSource,EventSource.id==Event.source_id).where(EventSource.name==source)
    if venue:q=q.where(Occurrence.venue.ilike("%"+venue+"%"))
    if price_max is not None:
        amount=Occurrence.price_max if price_match=="strict" else Occurrence.price_min
        q=q.where(amount.is_not(None),amount<=price_max)
    if age_max is not None:q=q.where(or_(Event.age_limit<=age_max,Event.age_limit.is_(None)) if include_unknown_age else Event.age_limit<=age_max)
    if age_exact is not None:q=q.where(or_(Event.age_limit==age_exact,Event.age_limit.is_(None)) if include_unknown_age else Event.age_limit==age_exact)
    if is_free:q=q.where(Occurrence.is_free.is_(True),Occurrence.price_min==0,Occurrence.price_max==0)
    if query:
        for word in correct_text(query).split():
            q=q.where(or_(Event.title.ilike('%'+word+'%'),Event.description.ilike('%'+word+'%')))
    for keyword in keywords:
        for word in keyword.split():q=q.where(or_(Event.title.ilike('%'+word+'%'),Event.description.ilike('%'+word+'%')))
    if venue_type=='museum':
        q=q.where(or_(Category.slug=='museum',and_(Category.slug.in_(['exhibition','tour']),or_(Occurrence.venue.ilike('%музе%'),Event.title.ilike('%музе%'),Occurrence.venue.ilike('%галере%'),Event.title.ilike('%галере%')))))
    elif venue_type=='park':q=q.where(or_(Category.slug.in_(['park','amusement']),Occurrence.venue.ilike('%парк%')))
    if organizers:
        ids=select(EventOrganizer.event_id).join(Organizer).where(func.lower(Organizer.name).in_([v.lower() for v in organizers]))
        q=q.where(Event.id.in_(ids))
    if interest_categories:
        ids=select(EventInterestCategory.event_id).join(InterestCategory,InterestCategory.id==EventInterestCategory.category_id).where(InterestCategory.slug.in_(interest_categories))
        q=q.where(Event.id.in_(ids))
    effective=case((Occurrence.starts_at<utcnow(),utcnow()),else_=Occurrence.starts_at)
    q=q.order_by(case((Occurrence.schedule_kind=='place',1),else_=0),effective,Occurrence.starts_at,Occurrence.id)
    result=list(s.scalars(q))
    if time_of_day:
        bounds={"morning":(6,12),"afternoon":(12,17),"evening":(17,24),"night":(0,6)};a,b=bounds[time_of_day]
        # Long source intervals are not invented evening sessions.
        result=[o for o in result if o.schedule_kind=="session" and (not o.ends_at or aware(o.ends_at)-aware(o.starts_at)<timedelta(days=1)) and a<=aware(o.starts_at).astimezone(MSK).hour<b]
    warm(s,result)
    if performers:
        patterns=[ARTISTS.get(name,re.escape(name)) for name in performers]
        result=[o for o in result if any(re.search(pattern,s.get(Event,o.event_id).title+" "+(s.get(Event,o.event_id).description or ""),re.I) for pattern in patterns)]
    if sort=="price":result.sort(key=lambda o:(o.price_min is None,o.price_min or 0,aware(o.starts_at)))
    return result

def card(s,o,user_id=None):
    e=s.get(Event,o.event_id);c=s.get(City,o.city_id);category=s.get(Category,e.category_id);source=s.get(EventSource,e.source_id)
    cache=warm(s,[o],user_id);orgs=cache["orgs"][e.id]
    tracked=cache["tracking"].get(user_id,{}).get(o.id)
    return {"match":interest_match(s,o,user_id),"id":e.id,"available_occurrences":s.info.get("occurrence_counts",{}).get(e.id,1),"genres":[{"slug":v.slug,"label":v.name} for v in cache["genres"][e.id]],"occurrence_id":o.id,"title":e.title,"city":c.slug,"city_name":c.name,"kind":e.kind,"schedule_kind":o.schedule_kind,"schedule_note":e.schedule_note,"starts_at":aware(o.starts_at).isoformat() if o.schedule_kind!="place" else None,"ends_at":aware(o.ends_at).isoformat() if o.ends_at else None,"place_name":o.venue,"address":o.address,"price_min":o.price_min,"price_max":o.price_max,"price_text":o.price_text,"is_free":o.is_free,"age_restriction":e.age_limit,"categories":[category.slug],"category_name":category.name,"image_url":e.image_url,"status":o.status,"is_demo":e.is_demo,"is_tracked":bool(tracked),"remind_at":aware(tracked.remind_at).isoformat() if tracked and tracked.remind_at else None,"organizers":[{"id":v.id,"name":v.name,"external_url":v.external_url} for v in orgs],"source":{"name":source.name,"url":o.external_url or e.external_url,"updated_at":aware(e.source_updated_at).isoformat() if e.source_updated_at else None,"fetched_at":aware(e.fetched_at).isoformat()}}

def preferences(s,user_id):
    p=s.scalar(select(UserPreference).where(UserPreference.user_id==user_id))
    return {"home_city":p.home_city if p else None,"include_nearby":p.include_nearby if p else False,"age_group_id":p.age_group_id if p else None,"budget_min":p.budget_min if p else None,"budget_max":p.budget_max if p else None,"interest_ids":list(s.scalars(select(UserInterest.interest_id).where(UserInterest.user_id==user_id))),"interest_category_ids":list(s.scalars(select(UserInterestCategory.category_id).where(UserInterestCategory.user_id==user_id))),"organizer_ids":list(s.scalars(select(UserOrganizer.organizer_id).where(UserOrganizer.user_id==user_id)))}

def ranking(s,o,p,intent=None):
    e=s.get(Event,o.event_id);cat=s.get(Category,e.category_id);score=10;reasons=[]
    if cat.interest_id in p.get("interest_ids",[]):score+=40;reasons.append("Совпадает с выбранным интересом: "+s.get(Interest,cat.interest_id).name)
    cache=warm(s,[o])
    matches=[g for g in cache["genres"][e.id] if g.id in p.get("interest_category_ids",[])]
    for m in matches:score+=10;reasons.append("Подтверждённая категория: "+m.name)
    orgs=[g for g in cache["orgs"][e.id] if g.id in p.get("organizer_ids",[])]
    for m in orgs:score+=20;reasons.append("Выбранная площадка или организатор: "+m.name)
    low,high=p.get("budget_min"),p.get("budget_max")
    if (low is not None or high is not None) and o.price_min is not None and o.price_max is not None and (low is None or o.price_min>=low) and (high is None or o.price_max<=high):
        score+=10;reasons.append("Указанный диапазон цен укладывается в бюджет профиля")
    if intent:
        if intent.categories:score+=20;reasons.append("Категория: "+cat.name)
        if intent.date_from:reasons.append("Период проведения пересекается с выбранной датой")
        if intent.time_of_day:reasons.append("Время начала соответствует выбранной части дня")
        cap=intent.budget_per_person
        if intent.budget_total is not None:cap=min(cap if cap is not None else intent.budget_total,intent.budget_total//intent.party_size)
        if cap is not None and o.price_min is not None and o.price_min<=cap:
            reasons.append(f"Билеты от {o.price_min} ₽ на человека; бюджет {cap} ₽. Наличие и условия — у источника.");score+=10
        if intent.free_only:reasons.append("Бесплатный вход подтверждён источником")
        if intent.performers:reasons.append("Исполнитель упомянут в названии или описании")
    if not reasons:reasons.append("Актуальный сеанс в выбранном городе")
    return min(100,score),reasons

def natural_results(s,intent,user_id,include_demo=False,relax=True):
    p=preferences(s,user_id) if user_id else {}
    caps=[x for x in [intent.budget_per_person,intent.budget_total//intent.party_size if intent.budget_total is not None else None] if x is not None]
    rows=query_occurrences(s,keywords=intent.keywords,venue_type=intent.venue_type,age_exact=intent.age_exact,city=intent.city,include_nearby=intent.include_nearby,date_from=intent.date_from,date_to=intent.date_to,categories=intent.categories,price_max=min(caps) if caps else None,is_free=intent.free_only,time_of_day=intent.time_of_day,organizers=intent.organizers,interest_categories=intent.interest_categories,include_demo=include_demo,excluded_categories=intent.excluded_categories,performers=intent.performers,age_max=intent.age_max,price_match=intent.price_match)
    rows=unique_events(s,rows);warm(s,rows,user_id)
    results=[]
    for o in rows:
        score,reasons=ranking(s,o,p,intent);results.append({"event":card(s,o,user_id),"score":score,"reasons":reasons})
    # The filtered catalogue order is chronological; profile scores explain fit only.
    relaxations=suggest_alternatives(s,intent,user_id,include_demo) if not results and relax else []
    return results,relaxations


def suggest_alternatives(s,intent,user_id,include_demo=False):
    variants=[]
    if intent.keywords or intent.performers:
        variants.append(('Другие события этой категории', {'keywords':[],'performers':[]}, 'Без имени или названия из запроса. Город и бюджет сохранены.'))
    if intent.date_from or intent.date_to or intent.time_of_day:
        variants.append(('В другой день', {'date_from':None,'date_to':None,'time_of_day':None}, 'Изменены только условия даты и времени.'))
    if intent.interest_categories or intent.venue_type or intent.organizers:
        variants.append(('Без уточнения темы или площадки', {'interest_categories':[],'venue_type':None,'organizers':[]}, 'Категория, город и бюджет сохранены.'))
    reset_subject={'categories':[],'interest_categories':[],'keywords':[],'performers':[],'venue_type':None,'organizers':[]}
    if any([intent.categories,intent.keywords,intent.performers,intent.venue_type,intent.interest_categories]):
        variants.append(('Другие идеи в вашем городе',reset_subject,'Категория изменена; бюджет и условие бесплатного входа сохранены.'))
        variants.append(('Другие идеи на ближайшие дни',{**reset_subject,'date_from':None,'date_to':None,'time_of_day':None},'Категория и даты изменены. Бюджет и условие бесплатного входа сохранены.'))
    if intent.budget_per_person is not None or intent.budget_total is not None:
        variants.append(('С другим бюджетом',{'budget_per_person':None,'budget_total':None},'Эти варианты могут быть дороже указанного бюджета.'))
    if intent.free_only:
        variants.append(('Платные варианты',{'free_only':False},'Здесь есть платные события: проверьте цену на карточке.'))
    variants.append(('Все идеи в этом городе',{**reset_subject,'date_from':None,'date_to':None,'time_of_day':None,'budget_per_person':None,'budget_total':None,'free_only':False,'age_exact':None,'age_max':None},'Показаны другие категории, даты и цены. Город сохранён.'))
    if not intent.include_nearby:
        variants.append(('В ближайших городах',{**reset_subject,'include_nearby':True,'date_from':None,'date_to':None,'time_of_day':None,'age_exact':None,'age_max':None},'Включены соседние города. Бюджет и бесплатный вход сохранены.'))
    found_groups=[];used=set()
    for label,patch,explanation in variants:
        candidate=intent.model_copy(update={**patch,'hard_constraints':[]})
        found,_=natural_results(s,candidate,user_id,include_demo,False)
        unique=[row['event'] for row in found if row['event']['id'] not in used]
        if not unique:continue
        shown=unique[:3];used.update(row['id'] for row in shown)
        found_groups.append({'label':label,'explanation':explanation,'estimated_count':len(found),'intent':candidate.model_dump(mode='json'),'events':shown})
        if len(found_groups)==2:break
    return found_groups
