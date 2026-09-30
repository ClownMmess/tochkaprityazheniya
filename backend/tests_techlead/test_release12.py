from datetime import date,datetime,timezone,timedelta
from pathlib import Path
import json
import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select,func
from app.db.base import Base,make_engine,utcnow
from app.models import Event,Occurrence,EventInterestCategory
from app.services.bootstrap import CATEGORIES,bootstrap
from app.integrations.llm.fallback import parse_fallback,guard_explicit
from app.integrations.llm.clarify import merge_context,questions
from app.integrations.llm.schemas import SearchIntent
from app.integrations.sources.kassir import parse_items
from app.integrations.kudago.importer import import_items,mark_missing
from app.services.catalog import query_occurrences,unique_events,card

@pytest.mark.parametrize('text,categories,genre',[
 ('Хочу сводить девушку в музей',{'museum','exhibition'},None),
 ('хочу на рэп концерт',{'concert'},'hip-hop'),('стенап до 3000',{'stand-up'},None),
 ('стеднап',{'stand-up'},None),('концрет',{'concert'},None),
 ('музеи',{'museum','exhibition'},None),('в мзуей',{'museum','exhibition'},None),
 ('ярморка',{'fair'},None),('ярмарки',{'fair'},None),
 ('парк развлечений',{'amusement'},None),('достопримечательности',{'landmark'},None),
 ('парки',{'park'},None),('Хочу на джаз',{'concert'},'jazz'),
 ('рэп',{'concert'},'hip-hop'),('спектакли',{'theater'},None),
 ('Бесплатные выставки',{'exhibition'},None),
])
def test_user_language_and_typos(text,categories,genre):
 intent=parse_fallback(text,'msk',date(2026,9,29),set(CATEGORIES))
 assert set(intent.categories)==categories
 if genre:assert genre in intent.interest_categories


def test_museum_is_guarded_against_wrong_model_and_followup_keeps_it():
 museum=parse_fallback('Хочу сводить девушку в музей','msk',date(2026,9,29),set(CATEGORIES))
 wrong=SearchIntent(city='krd',categories=['stand-up'],party_size=1)
 actual=guard_explicit(wrong,museum)
 assert actual.venue_type=='museum' and actual.party_size==2 and 'stand-up' not in actual.categories
 answer=parse_fallback('завтра до 2000 на человека','msk',date(2026,9,29),set(CATEGORIES))
 merged=merge_context(actual,answer)
 assert merged.categories==actual.categories and merged.party_size==2
 assert merged.budget_per_person==2000 and merged.date_from==date(2026,9,30)
 for q in questions(actual,date(2026,9,29)):
  assert all(o['intent']['venue_type']=='museum' and o['intent']['party_size']==2 for o in q['options'])


def test_source_preserves_real_age_price_and_local_clock():
 fixture=Path(__file__).parents[1]/'tests/fixtures/kassir-event.json'
 rows=parse_items(json.loads(fixture.read_text()),'msk',datetime(2026,9,29,tzinfo=timezone.utc))
 event=next(r for r in rows if r['title']=='The Beatles Festival')
 assert event['dates'][0]['start']==1791640800 # 17:00 Moscow, confirmed by official BASE page
 assert event['age_restriction']=='6+' and event['price']=='2500 рублей'


def test_places_are_undated_exact_ages_and_refresh_does_not_erase_places(tmp_path):
 engine=make_engine('sqlite:///'+str(tmp_path/'release.db'));Base.metadata.create_all(engine);sessions=sessionmaker(engine,expire_on_commit=False)
 now=utcnow()
 def row(i,age=None,kind='event'):
  return {'id':str(i),'title':'Музей '+str(i),'site_url':'https://kudago.com/msk/event/'+str(i),
   'age_restriction':age,'kind':kind,'categories':['museum'],'dates':[{'start':int((now+timedelta(days=i)).timestamp())}] if kind=='event' else [],
   'place':{'id':i,'title':'Музей '+str(i)}}
 with sessions.begin() as s:
  bootstrap(s);import_items(s,[row(1,0),row(2,'6+'),row(3,'16+'),row(4,None,'place')],'msk',now)
  assert len(query_occurrences(s,city='msk',age_exact=0))==1
  assert len(query_occurrences(s,city='msk',age_exact=16))==1
  assert len(query_occurrences(s,city='msk',age_max=16))==3
  place=query_occurrences(s,city='msk',kind='place')[0];data=card(s,place)
  assert data['starts_at'] is None and data['schedule_kind']=='place'
  mark_missing(s,'KudaGo','msk',[],now,kind='event');s.flush()
  assert query_occurrences(s,city='msk',kind='place')
  assert not query_occurrences(s,city='msk',kind='event')
 engine.dispose()


def test_scheduler_repeats_without_blocking_notifications():
 from app.integrations.sources.scheduler import run
 from app.config import Settings
 class Stop:
  count=0
  def is_set(self):return self.count==2
  def wait(self,interval):assert interval==21600;self.count+=1
 calls=[]
 run('sessions',Settings(),Stop(),refresh=lambda sessions,url:calls.append((sessions,url)))
 assert len(calls)==2


def test_dated_sessions_grouped_with_independent_price_and_ticket_link():
 from copy import deepcopy
 from app.integrations.sources.kassir import merge_row
 fixture=Path(__file__).parents[1]/'tests/fixtures/kassir-event.json'
 entry=json.loads(fixture.read_text())[0];second=deepcopy(entry)
 second['object']['id']+=100
 second['object']['beginsAt']='2026-11-10T17:00:00+00:00'
 second['object']['endsAt']='2026-11-10T23:00:00+00:00'
 second['object']['priceRange']={'min':3000,'max':5000}
 second['object']['url']='https://msk.kassir.ru/koncert/second-session'
 rows={}
 for item in parse_items([entry,second],'msk',datetime(2026,9,29,tzinfo=timezone.utc)):merge_row(rows,item)
 assert len(rows)==1
 dates=next(iter(rows.values()))['dates'];assert len(dates)==2
 assert dates[1]['source_url'].endswith('second-session') and dates[1]['price']=='3000–5000 рублей'
