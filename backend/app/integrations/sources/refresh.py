from app.integrations.sources.local_places import LOCAL_SOURCES,fetch_local
from app.services.locations import city_scope
"""Independent source transactions; failed/partial fetches never erase valid data."""
import os
from contextlib import contextmanager
from sqlalchemy import select, text
from app.models import ImportRun
from app.db.base import utcnow
from app.services.bootstrap import bootstrap,stable
from app.integrations.kudago.importer import fetch_city,import_items,mark_missing,normalize_schedule
from app.integrations.sources.venues import SOURCES,fetch_venue
from app.integrations.sources.timepad import fetch_timepad
from app.integrations.sources.culture import fetch_culture
from app.integrations.sources.places import fetch_places
from app.integrations.sources.nethouse import fetch_nethouse

@contextmanager
def import_lock(sessions):
    engine = sessions.kw['bind']
    if engine.dialect.name != 'postgresql':
        yield True
        return
    with engine.connect() as connection:
        acquired = connection.scalar(text('SELECT pg_try_advisory_lock(1296123462)'))
        try: yield bool(acquired)
        finally:
            if acquired: connection.execute(text('SELECT pg_advisory_unlock(1296123462)'))


def refresh_all(sessions,kudago_url):
    with import_lock(sessions) as acquired:
        if not acquired:
            return [{'status':'skipped','reason':'import_already_running'}]
        return _refresh(sessions,kudago_url)


def _refresh(sessions,kudago_url):
    results=[]
    sources=['KudaGo','Nethouse',*SOURCES,'ВДНХ','Музей «Гараж»',*LOCAL_SOURCES]
    if os.getenv('TIMEPAD_API_TOKEN'): sources.append('Timepad')
    enabled = {name.strip() for name in os.getenv('CATALOG_LIVE_SOURCES', 'KudaGo').split(',') if name.strip()}
    sources = [source for source in sources if source in enabled]
    for source in sources:
        cities=[LOCAL_SOURCES[source][1]] if source in LOCAL_SOURCES else ['msk','krd'] if source in {'KudaGo','Timepad','KASSIR.RU','Nethouse'} else ['krd' if source=='КРОП Арена' else 'msk']
        for city in cities:
            with sessions.begin() as s:
                bootstrap(s);run=ImportRun(source_id=stable('source',source),city_id=stable('city',city),status='running');s.add(run);s.flush();run_id=run.id
            try:
                fetched=utcnow()
                if source=='KudaGo':
                    rows,complete=fetch_city(kudago_url,city)
                    places,places_complete=fetch_places(kudago_url,city)
                    rows+=places;complete=complete and places_complete
                elif source=='Nethouse':rows,complete=fetch_nethouse(city,fetched)
                elif source in {'ВДНХ','Музей «Гараж»'}:rows,complete=fetch_culture(source,fetched)
                elif source in LOCAL_SOURCES:rows,complete=fetch_local(source,fetched)
                elif source=='Timepad':rows,complete=fetch_timepad(city,fetched,os.getenv('TIMEPAD_API_TOKEN'))
                else:rows,complete=fetch_venue(source,fetched),True
                rows=[normalize_schedule(row) for row in rows]
                with sessions.begin() as s:
                    count=0
                    targets=city_scope(city,True) if source=='KASSIR.RU' else [city]
                    for target in targets:
                        local=[r for r in rows if r.get('city',city)==target]
                        count+=import_items(s,local,target,fetched,source)
                        if complete:
                            kinds={'event','place'} if source=='KudaGo' else {'event'} if source=='KASSIR.RU' else {r.get('kind','event') for r in local}
                            for kind in kinds:
                                mark_missing(s,source,target,[r for r in local if r.get('kind','event')==kind],fetched,kind)
                    run=s.get(ImportRun,run_id);run.status='complete' if complete else 'partial';run.imported=count;run.finished_at=utcnow()
                result={'source':source,'city':city,'status':'complete' if complete else 'partial','imported':count}
            except Exception as exc:
                code=type(exc).__name__
                if getattr(exc,'response',None) is not None:code+='_'+str(exc.response.status_code)
                with sessions.begin() as s:
                    run=s.get(ImportRun,run_id);run.status='failed';run.error_code=code;run.finished_at=utcnow()
                result={'source':source,'city':city,'status':'failed','error':code,'catalog_preserved':True}
            results.append(result);print(result,flush=True)
    return results
