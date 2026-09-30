from app.services.locations import CITY_PATTERN, CITIES
import secrets
from datetime import date,timedelta
from uuid import UUID
from fastapi import APIRouter,Depends,Request,HTTPException,Query
from fastapi.responses import Response
from sqlalchemy import select,delete,func
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel,Field
from app.auth.dependencies import current_user_id
from app.auth.session import verify_session,issue_session,TTL
from app.auth.validation import VerifiedUser
from app.models import *
from app.db.base import utcnow,aware
from app.schemas.api import PreferencesIn,TrackIn,ChoiceIn,VoteIn,NaturalIn,PreviewIn
from app.services.catalog import card,option,is_actual,actual_clause,query_occurrences,preferences,ranking,natural_results,unique_events,warm,suggest_alternatives
from app.integrations.llm.schemas import SearchIntent
from app.integrations.llm.clarify import questions,merge_context
from app.integrations.sources.common import horizon
from zoneinfo import ZoneInfo

router=APIRouter()
def session(request:Request):
    with request.app.state.sessions() as s:yield s

def maybe_user(request:Request):
    value=request.headers.get("authorization","")
    if not value:return None
    return current_user_id(request)

def lock_user(s,user_id):
    if not s.scalar(select(User).where(User.id==user_id).with_for_update()):raise HTTPException(401,"invalid_session")
def selected_mode(request:Request,show_demo:bool):
    if show_demo and not request.app.state.settings.demo_mode:raise HTTPException(403,"demo_disabled")
    return show_demo

def user_json(s,u):
    p=s.scalar(select(UserPreference).where(UserPreference.user_id==u.id))
    return {"id":u.id,"max_user_id":u.max_user_id,"first_name":u.first_name,"onboarding_completed":bool(p and p.home_city),"home_city":p.home_city if p else None,"include_nearby":bool(p and p.include_nearby)}

@router.get('/runtime')
def runtime(request:Request,s=Depends(session)):
    counts={}
    for city in s.scalars(select(City)):
        counts[city.slug]=len(unique_events(s,query_occurrences(s,city=city.slug)))
    settings=request.app.state.settings
    return {"demo_mode":settings.demo_mode,"bot_name":settings.max_bot_name,"llm_enabled":settings.llm_enabled,"actual_occurrences":counts,"schema_version":5,"catalog_version":"1.3.1","horizon_end":horizon(utcnow()).date().isoformat(),"refresh_enabled":settings.catalog_refresh_enabled,"refresh_seconds":settings.catalog_refresh_seconds,"llm_model":settings.llm_model}

class DemoLogin(BaseModel):user: str=Field(pattern=r"^(pavel|anya)$")
@router.post('/auth/demo')
async def demo_auth(data:DemoLogin,request:Request):
    if not request.app.state.settings.demo_mode:raise HTTPException(404,"not_found")
    saved=await request.app.state.bindings.users.upsert_max_user(VerifiedUser(max_user_id='demo_'+data.user,first_name='Павел' if data.user=='pavel' else 'Аня'))
    return {"access_token":issue_session(saved['id'],request.app.state.settings.session_secret),"token_type":"bearer","expires_in":TTL,"user":saved}

@router.get('/meta')
def meta(s=Depends(session)):
    def items(model):return [{"id":x.id,"slug":x.slug,"label":x.name} for x in s.scalars(select(model).order_by(model.name))]
    return {"cities":[{**x,"area":CITIES[x["slug"]][1]} for x in items(City)],"categories":items(Category),"age_groups":items(AgeGroup),"interests":[{**v,"categories":[{"id":c.id,"slug":c.slug,"label":c.name} for c in s.scalars(select(InterestCategory).where(InterestCategory.interest_id==v['id']).order_by(InterestCategory.name))]} for v in items(Interest)],"sources":[{"label":x.name,"url":x.base_url,"loaded":x.last_sync_at is not None} for x in s.scalars(select(EventSource).where(EventSource.name!="Демонстрационные данные",EventSource.last_sync_at.is_not(None)).order_by(EventSource.name))],"organizers":[{"id":x.id,"label":x.name} for x in s.scalars(select(Organizer).order_by(Organizer.name))]}

@router.get('/me/preferences')
def get_preferences(user=Depends(current_user_id),s=Depends(session)):return preferences(s,user)

@router.put('/me/preferences')
def put_preferences(data:PreferencesIn,user=Depends(current_user_id),s=Depends(session)):
    lock_user(s,user)
    if not s.get(AgeGroup,str(data.age_group_id)):raise HTTPException(422,"invalid_filter")
    inputs=[(Interest,data.interest_ids),(InterestCategory,data.interest_category_ids),(Organizer,data.organizer_ids)]
    for model,ids in inputs:
        if any(not s.get(model,str(i)) for i in ids):raise HTTPException(422,"invalid_filter")
    parent_ids=set(str(v) for v in data.interest_ids)
    for i in data.interest_category_ids:parent_ids.add(s.get(InterestCategory,str(i)).interest_id)
    p=s.scalar(select(UserPreference).where(UserPreference.user_id==user))
    if not p:p=UserPreference(user_id=user);s.add(p)
    p.home_city=data.home_city;p.include_nearby=data.include_nearby;p.age_group_id=str(data.age_group_id);p.budget_min=data.budget_min;p.budget_max=data.budget_max
    for model,col,ids in [(UserInterest,'interest_id',parent_ids),(UserInterestCategory,'category_id',set(map(str,data.interest_category_ids))),(UserOrganizer,'organizer_id',set(map(str,data.organizer_ids)))]:
        s.execute(delete(model).where(model.user_id==user))
        for i in ids:s.add(model(**{'user_id':user,col:i}))
    s.commit();return preferences(s,user)

@router.get('/events')
def events(request:Request,city:str=Query('msk',pattern=CITY_PATTERN),include_nearby:bool=False,date_from:date|None=None,date_to:date|None=None,categories:list[str]=Query(default=[]),price_max:int|None=Query(None,ge=0),age_max:int|None=Query(None,ge=0,le=100),age_exact:int|None=Query(None,ge=0,le=100),include_unknown_age:bool=False,kind:str|None=Query(None,pattern="^(event|place)$"),is_free:bool=False,query:str=Query('',max_length=300),page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),interest_categories:list[str]=Query(default=[]),source:str|None=None,venue:str|None=None,time_of_day:str|None=Query(None,pattern="^(morning|afternoon|evening|night)$"),price_match:str=Query("from",pattern="^(from|strict)$"),sort:str=Query("date",pattern="^(date|price)$"),show_demo:bool=False,user=Depends(maybe_user),s=Depends(session)):
    if date_from and date_to and date_from>date_to:raise HTTPException(422,"invalid_filter")
    known=set(s.scalars(select(Category.slug)))
    if not set(interest_categories)<=set(s.scalars(select(InterestCategory.slug))):raise HTTPException(422,"invalid_filter")
    if not set(categories)<=known:raise HTTPException(422,"invalid_filter")
    rows=query_occurrences(s,age_exact=age_exact,include_unknown_age=include_unknown_age,kind=kind,city=city,include_nearby=include_nearby,date_from=date_from,date_to=date_to,categories=categories,price_max=price_max,age_max=age_max,is_free=is_free,query=query,include_demo=selected_mode(request,show_demo),interest_categories=interest_categories,source=source,venue=venue,time_of_day=time_of_day,price_match=price_match,sort=sort)
    rows=unique_events(s,rows);warm(s,rows,user)
    alternatives=[]
    if not rows and page==1:
        intent=SearchIntent(city=city,include_nearby=include_nearby,date_from=date_from,date_to=date_to,categories=categories,
                            budget_per_person=price_max,free_only=is_free,age_exact=age_exact,age_max=age_max,
                            interest_categories=interest_categories,time_of_day=time_of_day,keywords=[query] if query else [],price_match=price_match)
        alternatives=suggest_alternatives(s,intent,user,selected_mode(request,show_demo))
    return {"items":[card(s,o,user) for o in rows[(page-1)*page_size:page*page_size]],"page":page,"page_size":page_size,"total":len(rows),"alternatives":alternatives}

@router.get('/occurrences/{occurrence_id}')
def occurrence_detail(occurrence_id:UUID,user=Depends(maybe_user),s=Depends(session)):
    o=option(s,str(occurrence_id));e=s.get(Event,o.event_id)
    warm(s,[o],user)
    return {**card(s,o,user),"description":e.description,"occurrences":[card(s,v,user) for v in s.scalars(select(Occurrence).where(Occurrence.event_id==e.id,*actual_clause()).order_by(Occurrence.starts_at))]}

@router.get('/events/{event_id}')
def event_detail(event_id:UUID,user=Depends(maybe_user),s=Depends(session)):
    q=select(Occurrence).where(Occurrence.event_id==str(event_id))
    o=s.scalar(q.where(*actual_clause()).order_by(Occurrence.starts_at))
    if not o:o=s.scalar(q.order_by(Occurrence.starts_at.desc()))
    if not o:raise HTTPException(404,"event_not_found")
    return occurrence_detail(UUID(o.id),user,s)

class IntentRequest(BaseModel):
    intent:SearchIntent
    show_demo:bool=False
    page:int=Field(default=1,ge=1)
    page_size:int=Field(default=20,ge=1,le=100)

@router.post('/search/natural')
async def natural(data:NaturalIn,request:Request,show_demo:bool=False,user=Depends(maybe_user)):
    mode=selected_mode(request,show_demo)
    def taxonomy():
        with request.app.state.sessions() as s:return set(s.scalars(select(Category.slug))),set(s.scalars(select(InterestCategory.slug)))
    cats,genres=await run_in_threadpool(taxonomy)
    intent,status=await request.app.state.llm.search(data.text,data.city,cats,genres)
    intent.include_nearby=data.include_nearby
    def calculate():
        with request.app.state.sessions() as s:return natural_results(s,intent,user,mode)
    if data.context:
        intent=merge_context(data.context,intent)
    ambiguous=not intent.categories and not intent.performers and not intent.keywords and len(set(intent.hard_constraints)-{'city'})==0
    results,relaxations=await run_in_threadpool(calculate)
    if ambiguous:
        def alternatives():
            with request.app.state.sessions() as s:return suggest_alternatives(s,intent,user,mode)
        results=[];relaxations=await run_in_threadpool(alternatives)
    return {"intent":intent.model_dump(mode='json'),"results":results[:20],"total":len(results),"page":1,"page_size":20,"llm_status":status,"relaxations":relaxations,"questions":questions(intent,utcnow().astimezone(ZoneInfo("Europe/Moscow")).date())}

@router.post('/search/intent')
def search_intent(data:IntentRequest,request:Request,user=Depends(maybe_user),s=Depends(session)):
    if not set(data.intent.categories+data.intent.excluded_categories)<=set(s.scalars(select(Category.slug))):raise HTTPException(422,"invalid_filter")
    if not set(data.intent.interest_categories)<=set(s.scalars(select(InterestCategory.slug))):raise HTTPException(422,'invalid_filter')
    results,relaxations=natural_results(s,data.intent,user,selected_mode(request,data.show_demo))
    return {"intent":data.intent.model_dump(mode='json'),"results":results[(data.page-1)*data.page_size:data.page*data.page_size],"total":len(results),"page":data.page,"page_size":data.page_size,"llm_status":"filters","relaxations":relaxations,"questions":questions(data.intent,utcnow().astimezone(ZoneInfo("Europe/Moscow")).date())}

@router.post('/search/preview')
def search_preview(data:PreviewIn,s=Depends(session)):
    from app.services.discovery import autocomplete
    return autocomplete(data.text,data.city,set(s.scalars(select(Category.slug))),utcnow().astimezone(ZoneInfo("Europe/Moscow")).date(),data.include_nearby)

@router.get('/discovery')
def get_discovery(city:str=Query('msk',pattern=CITY_PATTERN),include_nearby:bool=False,seed:str=Query('0',max_length=80),user=Depends(maybe_user),s=Depends(session)):
    from app.services.discovery import discovery
    return discovery(s,city,include_nearby,user,seed)

@router.get('/me/tracked-events')
def tracked(user=Depends(current_user_id),s=Depends(session)):
    rows=list(s.scalars(select(Occurrence).join(TrackedEvent,TrackedEvent.occurrence_id==Occurrence.id).where(TrackedEvent.user_id==user,TrackedEvent.status=='active').order_by(Occurrence.starts_at)))
    return {"items":[card(s,o,user) for o in rows],"page":1,"page_size":max(1,len(rows)),"total":len(rows)}

@router.put('/me/tracked-events/{occurrence_id}')
def track(occurrence_id:UUID,data:TrackIn,user=Depends(current_user_id),s=Depends(session)):
    lock_user(s,user);o=option(s,str(occurrence_id))
    if not is_actual(o):raise HTTPException(409,"event_not_actual")
    t=s.scalar(select(TrackedEvent).where(TrackedEvent.user_id==user,TrackedEvent.occurrence_id==o.id))
    was_active=bool(t and t.status=='active')
    now=utcnow();desired=aware(o.starts_at)-timedelta(minutes=data.remind_before_minutes)
    if desired<now:
        # Keep an existing immediate reminder stable on retries, even hours later.
        desired=(aware(t.remind_at) if was_active and t.remind_at and aware(t.remind_at)<=now else now) if aware(o.starts_at)>now else None
    if not t:t=TrackedEvent(user_id=user,occurrence_id=o.id);s.add(t);s.flush()
    # Same active setting returns existing jobs: exact repeat is idempotent.
    equivalent=was_active and ((desired is None and t.remind_at is None) or (desired and t.remind_at and desired==aware(t.remind_at)))
    t.status='active'
    if not equivalent:
        t.remind_at=desired;t.is_notified=False
        for j in s.scalars(select(NotificationJob).where(NotificationJob.tracking_id==t.id,NotificationJob.status.in_(['pending','processing']))):j.status='cancelled'
        revision=secrets.token_hex(8)
        if not was_active:s.add(NotificationJob(user_id=user,occurrence_id=o.id,tracking_id=t.id,type='tracking_confirmation',scheduled_at=utcnow(),dedupe_key=f'{t.id}:confirmation:{revision}'))
        if desired:s.add(NotificationJob(user_id=user,occurrence_id=o.id,tracking_id=t.id,type='event_reminder',scheduled_at=desired,dedupe_key=f'{t.id}:reminder:{revision}'))
    s.commit();return card(s,o,user)

@router.delete('/me/tracked-events/{occurrence_id}',status_code=204)
def untrack(occurrence_id:UUID,user=Depends(current_user_id),s=Depends(session)):
    lock_user(s,user)
    t=s.scalar(select(TrackedEvent).where(TrackedEvent.user_id==user,TrackedEvent.occurrence_id==str(occurrence_id)))
    if t:
        t.status='cancelled'
        for j in s.scalars(select(NotificationJob).where(NotificationJob.tracking_id==t.id,NotificationJob.status.in_(['pending','processing']))):j.status='cancelled'
    s.commit();return Response(status_code=204)

@router.get('/occurrences/{occurrence_id}/community')
def community(occurrence_id:UUID,user=Depends(current_user_id),s=Depends(session)):
    o=option(s,str(occurrence_id))
    chat=s.scalar(select(EventChat).where(EventChat.event_id==o.event_id,EventChat.is_active.is_(True)))
    return {'invite_link':chat.invite_link if chat else None}

@router.post('/group-choices',status_code=201)
def create_choice(data:ChoiceIn,request:Request,user=Depends(current_user_id),s=Depends(session)):
    ids=list(map(str,data.occurrence_ids))
    if len(set(ids))!=len(ids) or not data.title.strip():raise HTTPException(422,'invalid_group_choice')
    rows=[option(s,i) for i in ids]
    if not all(is_actual(o) for o in rows):raise HTTPException(409,'event_not_actual')
    if len({o.event_id for o in rows})!=len(ids):raise HTTPException(422,'invalid_group_choice')
    c=GroupChoice(creator_id=user,title=data.title.strip(),description=data.description,public_token=secrets.token_urlsafe(24),expires_at=utcnow()+timedelta(days=7));s.add(c);s.flush();p=preferences(s,user)
    for o in rows:s.add(GroupChoiceEvent(choice_id=c.id,occurrence_id=o.id,recommendation_score=ranking(s,o,p)[0]))
    s.commit();return choice_response(s,c,user,request)

def get_choice(s,token,lock=False):
    q=select(GroupChoice).where(GroupChoice.public_token==token)
    c=s.scalar(q.with_for_update() if lock else q)
    if not c:raise HTTPException(404,'choice_not_found')
    return c

def choice_response(s,c,user,request):
    opts=list(s.scalars(select(GroupChoiceEvent).where(GroupChoiceEvent.choice_id==c.id).order_by(GroupChoiceEvent.recommendation_score.desc(),GroupChoiceEvent.occurrence_id)))
    mine=list(s.scalars(select(GroupChoiceVote.occurrence_id).where(GroupChoiceVote.choice_id==c.id,GroupChoiceVote.user_id==user))) if user else []
    visible=bool(mine)
    votes=dict(s.execute(select(GroupChoiceVote.occurrence_id,func.count()).where(GroupChoiceVote.choice_id==c.id).group_by(GroupChoiceVote.occurrence_id)).all()) if visible else {}
    voters=s.scalar(select(func.count(func.distinct(GroupChoiceVote.user_id))).where(GroupChoiceVote.choice_id==c.id)) if visible else None
    settings=request.app.state.settings
    web=settings.public_app_url.rstrip('/')+'/?choice='+c.public_token
    deep='https://max.ru/'+settings.max_bot_name+'?startapp=choice_'+c.public_token if settings.max_bot_name and not settings.demo_mode else None
    # Order is independent of votes; a hidden result cannot be inferred from card positions.
    return {'id':c.id,'title':c.title,'public_token':c.public_token,'deep_link':deep,'web_link':web,
            'events':[{'event':card(s,option(s,o.occurrence_id),user),'votes':votes.get(o.occurrence_id,0) if visible else None} for o in opts],
            'my_votes':mine,'results_visible':visible,'voter_count':voters,
            'total_votes':sum(votes.values()) if visible else None,
            'expires_at':aware(c.expires_at).isoformat(),'status':'expired' if aware(c.expires_at)<=utcnow() else c.status}

@router.get('/group-choices/{token}')
def read_choice(token:str,request:Request,user=Depends(maybe_user),s=Depends(session)):
    return choice_response(s,get_choice(s,token),user,request)

def voting_choice(s,token,oid):
    choice=get_choice(s,token,True)
    if choice.status!='active' or aware(choice.expires_at)<=utcnow():raise HTTPException(409,'choice_expired')
    if not s.get(GroupChoiceEvent,(choice.id,oid)):raise HTTPException(422,'invalid_group_choice')
    return choice

@router.put('/group-choices/{token}/vote')
def vote(token:str,data:VoteIn,request:Request,user=Depends(current_user_id),s=Depends(session)):
    oid=str(data.occurrence_id);choice=voting_choice(s,token,oid)
    if not is_actual(option(s,oid)):raise HTTPException(409,'event_not_actual')
    existing=s.scalar(select(GroupChoiceVote).where(GroupChoiceVote.choice_id==choice.id,GroupChoiceVote.user_id==user,GroupChoiceVote.occurrence_id==oid))
    if not existing:s.add(GroupChoiceVote(choice_id=choice.id,user_id=user,occurrence_id=oid))
    s.commit();return choice_response(s,choice,user,request)

@router.delete('/group-choices/{token}/votes/{occurrence_id}')
def remove_vote(token:str,occurrence_id:UUID,request:Request,user=Depends(current_user_id),s=Depends(session)):
    oid=str(occurrence_id);choice=voting_choice(s,token,oid)
    s.execute(delete(GroupChoiceVote).where(GroupChoiceVote.choice_id==choice.id,GroupChoiceVote.user_id==user,GroupChoiceVote.occurrence_id==oid))
    s.commit();return choice_response(s,choice,user,request)

@router.get('/me/notifications')
def notifications(user=Depends(current_user_id),s=Depends(session)):
    rows=s.scalars(select(NotificationJob).where(NotificationJob.user_id==user).order_by(NotificationJob.created_at.desc()).limit(100))
    return {'items':[{'id':j.id,'type':j.type,'scheduled_at':aware(j.scheduled_at).isoformat(),'status':j.status,'event':card(s,option(s,j.occurrence_id),user),'error_code':j.last_error_code} for j in rows]}

@router.get('/sources')
def sources_status(city:str=Query('msk',pattern=CITY_PATTERN),s=Depends(session)):
    rows=unique_events(s,query_occurrences(s,city=city));counts={}
    for row in rows:
        event=s.get(Event,row.event_id);key=event.source_id
        entry=counts.setdefault(key,{'events':0,'places':0})
        entry['places' if event.kind=='place' else 'events']+=1
    result=[]
    for source in s.scalars(select(EventSource).where(EventSource.name!='Демонстрационные данные').order_by(EventSource.name)):
        latest=s.scalar(select(ImportRun).join(City,City.id==ImportRun.city_id).where(ImportRun.source_id==source.id,City.slug==city).order_by(ImportRun.started_at.desc()).limit(1))
        result.append({'name':source.name,'url':source.base_url,**counts.get(source.id,{'events':0,'places':0}),
            'last_sync_at':aware(source.last_sync_at).isoformat() if source.last_sync_at else None,
            'status':latest.status if latest else 'snapshot' if source.last_sync_at else 'not_connected',
            'last_attempt_at':aware(latest.started_at).isoformat() if latest else None,
            'error':latest.error_code if latest else None})
    return {'items':result,'horizon_end':horizon(utcnow()).date().isoformat()}
