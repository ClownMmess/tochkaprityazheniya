import asyncio,os,json,secrets
from datetime import timedelta
from pathlib import Path
import pytest
from sqlalchemy import select,func,delete
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.auth.session import issue_session
from app.db.base import utcnow,make_engine,Base
from app.models import *
from app.services.bootstrap import bootstrap,stable
from app.services.demo import seed_demo
from app.integrations.kudago.importer import load_snapshot,price
from app.worker.runner import process_one
from app.bot.dispatcher import Dispatcher
from app.integrations.max.preview import PreviewMaxClient
from app.integrations.llm.adapter import OllamaAdapter
import httpx

SECRET='integration-test-secret-at-least-32-bytes'
@pytest.fixture(scope='module')
def ctx(tmp_path_factory):
    db=os.getenv('TEST_DATABASE_URL') or 'sqlite:///'+str(tmp_path_factory.mktemp('db')/'test.db')
    settings=Settings(database_url=db,session_secret=SECRET,demo_mode=True,llm_enabled=False,app_env='development',max_webhook_secret='testsecret')
    app=create_app(settings)
    if db.startswith('sqlite'):Base.metadata.create_all(app.state.bindings.engine)
    with app.state.sessions.begin() as s:bootstrap(s);seed_demo(s)
    with TestClient(app,raise_server_exceptions=True) as client:yield app,client

@pytest.fixture
def env(ctx):
    app,client=ctx
    with app.state.sessions.begin() as s:
        user=User(max_user_id='demo_test_'+secrets.token_hex(8),first_name='Проверка');s.add(user);s.flush();uid=user.id
    headers={'Authorization':'Bearer '+issue_session(uid,SECRET)}
    return app,client,uid,headers

def demo_ids(c):return [x['occurrence_id'] for x in c.get('/api/v1/events?show_demo=true&city=msk').json()['items']]

def test_metadata_normalized_preferences(env):
    app,c,u,h=env;m=c.get('/api/v1/meta').json()
    interest=next(x for x in m['interests'] if x['categories'])
    data={'age_group_id':m['age_groups'][0]['id'],'interest_ids':[],'interest_category_ids':[interest['categories'][0]['id']],'organizer_ids':[],'budget_min':0,'budget_max':1200}
    assert c.put('/api/v1/me/preferences',headers=h,json=data).status_code==200
    got=c.get('/api/v1/me/preferences',headers=h).json()
    assert interest['id'] in got['interest_ids']
    assert got['budget_min']==0 and got['budget_max']==1200
    data['interest_category_ids']=[];data['interest_ids']=[]
    c.put('/api/v1/me/preferences',headers=h,json=data)
    assert not c.get('/api/v1/me/preferences',headers=h).json()['interest_category_ids']

def test_filters_and_unknown_price(env):
    app,c,u,h=env
    data=c.get('/api/v1/events?show_demo=true&city=msk&price_max=0&age_max=18&is_free=true').json()
    assert data['items'] and all(x['is_free'] and x['price_max']==0 and x['city']=='msk' for x in data['items'])
    assert c.get('/api/v1/events?categories=does-not-exist').status_code==422
    assert c.get('/api/v1/events?date_from=2026-12-31&date_to=2026-01-01').status_code==422
    with app.state.sessions.begin() as s:
        o=s.get(Occurrence,data['items'][0]['occurrence_id']);old=o.price_max;o.price_max=None
    got=c.get('/api/v1/events?show_demo=true&city=msk&price_max=0&price_match=strict').json()
    assert data['items'][0]['occurrence_id'] not in [v['occurrence_id'] for v in got['items']]
    with app.state.sessions.begin() as s:s.get(Occurrence,data['items'][0]['occurrence_id']).price_max=old

def test_tracking_repeat_and_cancellation(env):
    app,c,u,h=env;oid=demo_ids(c)[0];url='/api/v1/me/tracked-events/'+oid
    for _ in range(2):assert c.put(url,headers=h,json={'remind_before_minutes':60}).status_code==200
    with app.state.sessions() as s:
        assert s.scalar(select(func.count()).select_from(TrackedEvent).where(TrackedEvent.user_id==u))==1
        assert s.scalar(select(func.count()).select_from(NotificationJob).where(NotificationJob.user_id==u))==2
    assert c.delete(url,headers=h).status_code==204
    with app.state.sessions() as s:assert all(j.status=='cancelled' for j in s.scalars(select(NotificationJob).where(NotificationJob.user_id==u)))
    assert not c.get('/api/v1/me/tracked-events',headers=h).json()['items']

def test_community_authorization(env):
    app,c,u,h=env;oid=demo_ids(c)[0]
    with app.state.sessions.begin() as s:
        o=s.get(Occurrence,oid);chat=EventChat(event_id=o.event_id,max_chat_id='-test'+secrets.token_hex(8),invite_link='https://max.ru/test-only');s.add(chat)
    url='/api/v1/occurrences/'+oid+'/community'
    assert c.get(url,headers=h).status_code==403
    c.put('/api/v1/me/tracked-events/'+oid,headers=h,json={'remind_before_minutes':60})
    assert c.get(url,headers=h).json()['invite_link']=='https://max.ru/test-only'
    with app.state.sessions.begin() as s:s.execute(delete(EventChat).where(EventChat.max_chat_id.like('-test%')))

def test_choice_two_users_vote_change_tie_expiry(env):
    app,c,u,h=env;ids=demo_ids(c)[:3]
    assert c.post('/api/v1/group-choices',headers=h,json={'title':'Выбор','occurrence_ids':[ids[0]]*3}).status_code==422
    r=c.post('/api/v1/group-choices',headers=h,json={'title':'Выбор','occurrence_ids':ids});assert r.status_code==201,r.text;data=r.json();token=data['public_token'];url='/api/v1/group-choices/'+token
    assert data['winner_occurrence_id'] is None
    a=c.put(url+'/vote',headers=h,json={'occurrence_id':ids[0]}).json();assert a['total_votes']==1
    a=c.put(url+'/vote',headers=h,json={'occurrence_id':ids[1]}).json();assert a['total_votes']==1 and a['my_vote']==ids[1]
    b=c.post('/api/v1/auth/demo',json={'user':'anya'}).json();h2={'Authorization':'Bearer '+b['access_token']}
    a=c.put(url+'/vote',headers=h2,json={'occurrence_id':ids[0]}).json();assert a['total_votes']==2
    assert a['winner_occurrence_id']==min(ids[:2])
    with app.state.sessions.begin() as s:s.get(GroupChoice,data['id']).expires_at=utcnow()-timedelta(seconds=1)
    assert c.put(url+'/vote',headers=h,json={'occurrence_id':ids[2]}).status_code==409

def test_full_intent_relaxation_preserves_other_constraints(env):
    app,c,u,h=env
    intent={'city':'msk','date_from':'2099-01-01','date_to':'2099-01-01','free_only':True}
    r=c.post('/api/v1/search/intent',headers=h,json={'intent':intent,'show_demo':True}).json();assert not r['results']
    assert r['relaxations']
    for relax in r['relaxations']:
        assert relax['estimated_count']>0
        repeated=c.post('/api/v1/search/intent',headers=h,json={'intent':relax['intent'],'show_demo':True}).json()
        assert len(repeated['results'])==relax['estimated_count']
        assert all(x['event']['is_free'] for x in repeated['results'])

def test_natural_fallback_real_database(env):
    app,c,u,h=env;r=c.post('/api/v1/search/natural?show_demo=true',headers=h,json={'text':'Бесплатно в Москве','city':'msk'})
    assert r.status_code==200,r.text
    assert r.json()['llm_status']=='fallback' and r.json()['results']
    assert all(x['event']['is_free'] for x in r.json()['results'])

def test_real_snapshot_idempotent_and_separate(env):
    app,c,u,h=env;path=Path(__file__).resolve().parents[2]/'seed/kudago_snapshot.json'
    with app.state.sessions.begin() as s:
        load_snapshot(s,path);before=s.scalar(select(func.count()).select_from(Event));load_snapshot(s,path);after=s.scalar(select(func.count()).select_from(Event));assert before==after
    live=c.get('/api/v1/events?city=msk').json();assert live['items'] and not any(x['is_demo'] for x in live['items'])
    assert all(x['source']['url'].startswith('https://kudago.com/') and x['source']['fetched_at'] for x in live['items'])

def test_notification_worker_preview(env):
    app,c,u,h=env;oid=demo_ids(c)[1];c.put('/api/v1/me/tracked-events/'+oid,headers=h,json={'remind_before_minutes':60})
    async def run():
        async with httpx.AsyncClient() as http:
            dispatcher=Dispatcher(PreviewMaxClient(),OllamaAdapter(http,'http://localhost/v1','test',enabled=False),app.state.bindings.bot,'')
            for _ in range(30):
                if not await process_one(app.state.bindings.jobs,dispatcher):break
    asyncio.run(run())
    notes=c.get('/api/v1/me/notifications',headers=h).json()['items'];assert any(x['type']=='tracking_confirmation' and x['status']=='preview' for x in notes)

def test_queue_dedupe_lease_and_redaction(env):
    app,c,u,h=env;store=app.state.bindings.jobs
    async def run():
        p={'chat_type':'dialog','update_type':'bot_started','chat_id':'123','user_id':'123'}
        key=secrets.token_hex(32)
        assert await store.enqueue_webhook(key,p)
        assert not await store.enqueue_webhook(key,p)
        job=await store.claim(90);assert job is not None
        from app.ports import Job as RuntimeJob
        await store.complete(RuntimeJob(job.id,'wrong-lease',job.kind,job.payload,job.attempts))
        with app.state.sessions() as s:assert s.get(Job,job.id[2:]).status=='processing'
        await store.complete(job)
        with app.state.sessions() as s:
            row=s.get(Job,job.id[2:]);assert row.status=='done' and row.payload=={}
        assert not await store.enqueue_webhook(key,p)
    asyncio.run(run())

def test_no_foreign_choice_vote_and_report(env):
    app,c,u,h=env;ids=demo_ids(c)
    choice=c.post('/api/v1/group-choices',headers=h,json={'title':'Тест','occurrence_ids':ids[:3]}).json()
    assert c.put('/api/v1/group-choices/'+choice['public_token']+'/vote',headers=h,json={'occurrence_id':ids[3]}).status_code==422
    assert c.post('/api/v1/occurrences/'+ids[0]+'/report',headers=h,json={'reason':'wrong_date'}).status_code==201
    assert c.get('/api/v1/occurrences/'+ids[0]+'/calendar.ics').text.startswith('BEGIN:VCALENDAR')

def test_demo_login_disabled_production():
    with pytest.raises(ValueError):Settings(app_env='production',demo_mode=True,session_secret=SECRET)

def test_strict_price_parser():
    assert price('800–1500 рублей',False)==(800,1500)
    assert price('от 500 рублей',False)==(500,None)
    assert price('детям 300, взрослым 800 рублей',False)==(None,None)

def test_late_reminder_repeat_does_not_create_another_job(env):
    app,c,u,h=env;oid=demo_ids(c)[0];url='/api/v1/me/tracked-events/'+oid
    with app.state.sessions.begin() as s:
        o=s.get(Occurrence,oid);original=o.starts_at;o.starts_at=utcnow()+timedelta(minutes=10)
    try:
        assert c.put(url,headers=h,json={'remind_before_minutes':60}).status_code==200
        with app.state.sessions.begin() as s:
            t=s.scalar(select(TrackedEvent).where(TrackedEvent.user_id==u));t.remind_at=utcnow()-timedelta(minutes=5)
            count=s.scalar(select(func.count()).select_from(NotificationJob).where(NotificationJob.user_id==u))
        assert c.put(url,headers=h,json={'remind_before_minutes':60}).status_code==200
        with app.state.sessions() as s:
            assert s.scalar(select(func.count()).select_from(NotificationJob).where(NotificationJob.user_id==u))==count
    finally:
        c.delete(url,headers=h)
        with app.state.sessions.begin() as s:s.get(Occurrence,oid).starts_at=original

def test_group_compatibility_uses_saved_profiles(env):
    app,c,u,h=env;ids=demo_ids(c)[:3];m=c.get('/api/v1/meta').json()
    with app.state.sessions() as s:
        event=s.get(Event,s.get(Occurrence,ids[0]).event_id);interest=s.get(Category,event.category_id).interest_id
    assert c.put('/api/v1/me/preferences',headers=h,json={'age_group_id':m['age_groups'][0]['id'],'interest_ids':[interest]}).status_code==200
    choice=c.post('/api/v1/group-choices',headers=h,json={'title':'Профили группы','occurrence_ids':ids}).json()
    chosen=next(x for x in choice['events'] if x['event']['occurrence_id']==ids[0])
    assert chosen['compatibility']=={'participants':1,'matched':1,'average_score':50}
    assert all('user_id' not in x['compatibility'] for x in choice['events'])

def test_existing_demo_session_blocked_after_mode_switch(env):
    app,c,u,h=env
    assert c.get('/api/v1/me/preferences',headers=h).status_code==200
    app.state.settings.demo_mode=False
    try:
        assert c.get('/api/v1/me/preferences',headers=h).status_code==401
        assert c.post('/api/v1/auth/demo',json={'user':'pavel'}).status_code==404
    finally:app.state.settings.demo_mode=True

def test_moderation_scope_cleanup_and_expired_lease(env):
    app,c,u,h=env;oid=demo_ids(c)[0];store=app.state.bindings.jobs;chat='-moderation-'+secrets.token_hex(8)
    with app.state.sessions.begin() as s:
        s.add(EventChat(event_id=s.get(Occurrence,oid).event_id,max_chat_id=chat,invite_link='https://max.ru/test-only'))
    payload={'update_type':'message_created','chat_type':'chat','chat_id':chat,'user_id':'123','message_id':secrets.token_hex(8),'text':' '.join(['https://test.invalid/ad']*5)}
    key=secrets.token_hex(32)
    async def run():
        assert not await store.enqueue_webhook(secrets.token_hex(32),{**payload,'chat_id':'unknown'})
        assert await store.enqueue_webhook(key,payload)
        async with httpx.AsyncClient() as http:
            dispatch=Dispatcher(PreviewMaxClient(),OllamaAdapter(http,'http://localhost/v1','test',enabled=False),store,'')
            for _ in range(30):
                if not await process_one(store,dispatch):break
        with app.state.sessions() as s:
            row=s.scalar(select(Job).where(Job.dedupe_key==key));assert row.status=='done' and row.payload=={}
            log=s.scalar(select(ModerationLog).where(ModerationLog.job_id==row.id))
            assert log.decision=='delete' and log.reason=='spam'
            assert payload['text'] not in log.model_response and 'https://' not in log.model_response
        stale_key=secrets.token_hex(32);assert await store.enqueue_webhook(stale_key,{**payload,'text':'обычное сообщение'})
        job=await store.claim(90)
        with app.state.sessions.begin() as s:s.get(Job,job.id[2:]).locked_until=utcnow()-timedelta(seconds=1)
        await store.purge_expired_payloads();await store.complete(job)
        with app.state.sessions() as s:
            row=s.get(Job,job.id[2:]);assert row.status=='review' and row.payload=={} and row.lease_token is None
    try:asyncio.run(run())
    finally:
        with app.state.sessions.begin() as s:s.execute(delete(EventChat).where(EventChat.max_chat_id==chat))


def test_user_search_examples_keep_exact_constraints(env):
    app,c,u,h=env
    samples=[('бесплатно',None,None),('стендап до 3000',{'stand-up'},3000),('хочу сводить девушку на свидание на стендап или в театр до 5000',{'stand-up','theater'},2500)]
    for text,categories,cap in samples:
        data=c.post('/api/v1/search/natural',json={'text':text,'city':'msk'},headers=h).json()
        assert data['total']>0,(text,data)
        assert len({r['event']['id'] for r in data['results']})==len(data['results'])
        if categories:assert set(data['intent']['categories'])==categories
        for row in data['results']:
            event=row['event']
            if categories:assert set(event['categories'])<=categories
            if cap is not None:assert event['price_min'] is not None and event['price_min']<=cap
            if text=='бесплатно':assert event['is_free']
        if text.startswith('хочу'):assert data['intent']['party_size']==2
        if data['total']>data['page_size']:
            second=c.post('/api/v1/search/intent',json={'intent':data['intent'],'page':2},headers=h).json()
            assert second['total']==data['total']
            assert not {r['event']['id'] for r in data['results']}&{r['event']['id'] for r in second['results']}


def test_five_distinct_events_group_and_limits(env):
    app,c,u,h=env;ids=demo_ids(c)[:5]
    assert len(ids)==5
    data=c.post('/api/v1/group-choices',headers=h,json={'title':'Пять вариантов','occurrence_ids':ids})
    assert data.status_code==201,data.text
    group=data.json();assert len(group['events'])==5
    voted=c.put('/api/v1/group-choices/'+group['public_token']+'/vote',headers=h,json={'occurrence_id':ids[4]})
    assert voted.json()['my_vote']==ids[4]
    for bad in ([ids[0]],ids+[ids[0]],[ids[0],ids[0]]):
        assert c.post('/api/v1/group-choices',headers=h,json={'title':'Неверно','occurrence_ids':bad}).status_code==422


def test_venues_real_snapshot_artists_and_source_filter(env):
    from app.integrations.kudago.importer import load_venues_snapshot
    app,c,u,h=env;path=Path(__file__).resolve().parents[2]/'seed/venues_snapshot.json'
    with app.state.sessions.begin() as s:
        load_venues_snapshot(s,path);before=s.scalar(select(func.count()).select_from(Event));load_venues_snapshot(s,path)
        assert s.scalar(select(func.count()).select_from(Event))==before
    for artist,city,source in [('madk1d','msk','BASE'),('бульвар депо','msk','VK Stadium'),('Boulevard Depo','krd','КРОП Арена')]:
        data=c.post('/api/v1/search/natural',json={'text':artist,'city':city}).json()
        assert data['results'],(artist,data)
        assert all(r['event']['source']['name']==source for r in data['results'])
    data=c.get('/api/v1/events',params={'city':'krd','source':'КРОП Арена'}).json()
    assert data['total']>=30
    assert all(r['source']['name']=='КРОП Арена' for r in data['items'])


def test_catalogue_collapses_sessions_but_keeps_detail_and_filters(env):
    app,c,u,h=env
    rows=c.get('/api/v1/events?city=msk&page_size=100').json()['items']
    assert len({r['id'] for r in rows})==len(rows)
    repeated=next(r for r in rows if r['available_occurrences']>1)
    detail=c.get('/api/v1/occurrences/'+repeated['occurrence_id']).json()
    assert len(detail['occurrences'])>=repeated['available_occurrences']
    assert all(r['id']==repeated['id'] for r in detail['occurrences'])
    rows=c.get('/api/v1/events?city=msk&interest_categories=jazz').json()['items']
    assert rows and all(any(g['slug']=='jazz' for g in r['genres']) for r in rows)


def test_standup_source_real_sessions_keep_their_prices(env):
    app,c,u,h=env
    rows=c.get('/api/v1/events',params={'source':'StandUp Cafe','city':'msk','page_size':100}).json()['items']
    assert len(rows)>=30
    assert len({x['title'] for x in rows})==len(rows)
    assert all(x['price_min'] is not None and x['source']['url']=='https://standupcafe.ru/events' for x in rows)
    result=c.post('/api/v1/search/natural',json={'text':'стендап до 3000','city':'msk'}).json()
    assert result['total']>=20
    assert all(x['event']['categories']==['stand-up'] for x in result['results'])


def test_poster_endpoint_rejects_unknown_and_untrusted_urls(env):
    app,c,u,h=env
    assert c.get('/api/v1/events/00000000-0000-0000-0000-000000000000/image').status_code==404
    oid=demo_ids(c)[0]
    with app.state.sessions.begin() as s:
        occurrence=s.get(Occurrence,oid);event=s.get(Event,occurrence.event_id);event.image_url='https://localhost/private';eid=event.id
    assert c.get('/api/v1/events/'+eid+'/image').status_code==404

async def test_saved_place_has_confirmation_without_fake_date_or_reminder(env):
    from app.integrations.kudago.importer import import_items
    from app.ports import Job as ClaimedJob
    app,c,u,h=env
    ident='place-'+secrets.token_hex(6)
    with app.state.sessions.begin() as s:
        import_items(s,[{'id':ident,'title':'Музей без фиксированного сеанса','site_url':'https://kudago.com/msk/place/test-place/','kind':'place','categories':['museum'],'dates':[],'schedule_note':'Вт–Вс, часы на странице музея'}],'msk',utcnow())
        occurrence=s.scalar(select(Occurrence).join(Event).where(Event.external_id==ident));oid=occurrence.id
    saved=c.put('/api/v1/me/tracked-events/'+oid,headers=h,json={'remind_before_minutes':60})
    assert saved.status_code==200 and saved.json()['starts_at'] is None
    with app.state.sessions.begin() as s:
        jobs=list(s.scalars(select(NotificationJob).where(NotificationJob.user_id==u,NotificationJob.occurrence_id==oid)))
        assert len(jobs)==1 and jobs[0].type=='tracking_confirmation'
        jobs[0].status='processing';jobs[0].lease_token='place-test';jid=jobs[0].id
    notice=await app.state.bindings.jobs.notification(ClaimedJob('n:'+jid,'place-test','tracking_confirmation',{},1))
    assert 'Вы сохранили место' in notice['text'] and '1970' not in notice['text']
    assert c.get('/api/v1/occurrences/'+oid+'/calendar.ics').status_code==409
