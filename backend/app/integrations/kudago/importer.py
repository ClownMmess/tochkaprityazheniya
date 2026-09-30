import html,json,re
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import select, delete
import httpx
from app.models import *
from app.db.base import utcnow,aware
from app.services.bootstrap import stable,bootstrap,CATEGORIES,CATEGORY_GENRES
from app.integrations.llm.fallback import CATEGORY_PATTERNS,GENRE_PATTERNS

def clean(v): return html.unescape(re.sub(r"<[^>]+>"," ",str(v or ""))).strip()
from app.services.prices import normalize_price

def price(raw, free):
    return normalize_price(raw, free)[:2]


def normalize_schedule(raw):
    dates = raw.get('dates', [])
    # KudaGo uses year 1 / year 9999 for a permanent programme with no session date.
    undated = dates and all(isinstance(d.get('start'), (int, float)) and d['start'] <= 0
                            and isinstance(d.get('end'), (int, float)) and d['end'] > utcnow().timestamp() for d in dates)
    if undated:
        return {**raw, 'kind': 'place', 'dates': [],
                'schedule_note': 'Постоянная программа в каталоге источника. Даты и часы посещения уточняйте у организатора.'}
    return raw


def event_key(source,external_id):
    return stable("kudago-event" if source=="KudaGo" else "source-event/"+source,external_id)

def import_items(s,items,city_slug,fetched_at,source_name="KudaGo"):
    """Idempotent normalized import; all adapters keep original URLs and source identity."""
    bootstrap(s);now=utcnow();n=0
    source_id=stable("source",source_name)
    # Keep objects alive for the whole import. Avoid a SELECT for every historical date.
    existing={e.id:e for e in s.scalars(select(Event).where(Event.source_id==source_id))}
    occurrences={o.id:o for o in s.scalars(select(Occurrence).join(Event).where(Event.source_id==source_id,Occurrence.city_id==stable("city",city_slug)))}
    per_event={}
    for occ in occurrences.values():per_event.setdefault(occ.event_id,[]).append(occ)
    orgs={o.id:o for o in s.scalars(select(Organizer))}
    by_url={o.external_url:o for o in orgs.values() if o.external_url}
    org_links=set(s.execute(select(EventOrganizer.event_id,EventOrganizer.organizer_id)).all())
    genre_links=set(s.execute(select(EventInterestCategory.event_id,EventInterestCategory.category_id)).all())
    known_genres=set(s.scalars(select(InterestCategory.id)))
    for original in items:
        raw=normalize_schedule(original)
        if not raw.get("id") or not raw.get("site_url") or not raw.get("title"):continue
        slug=next((x for x in raw.get("categories",[]) if x in CATEGORIES),"entertainment")
        slug={'yarmarki-razvlecheniya-yarmarki':'fair'}.get(slug,slug)
        title=clean(raw["title"]).casefold().replace("ё","е")
        if re.search(r'экскурси',title) and slug in {'tour','entertainment'}:slug='tour'
        elif re.search(CATEGORY_PATTERNS["stand-up"],title):slug="stand-up"
        elif re.search(r"спектакл|театраль|мюзикл",title):slug="theater"
        elif slug in {'entertainment','exhibition','festival','fair'} and re.search(r'ярмарк|\bмаркет\b',title):slug='fair'
        elif slug in {'entertainment','tour'} and re.search(r'\bпарк\b',title) and not re.search(r'экскурси|прогулк',title):slug='amusement' if 'аттракцион' in title else 'park'
        elif not raw.get("categories"):
            slug=next((key for key,pattern in CATEGORY_PATTERNS.items() if key in CATEGORIES and re.search(pattern,title)),"entertainment")
        event_id=event_key(source_name,raw["id"])
        event=existing.get(event_id)
        if event and (aware(event.fetched_at)>fetched_at or (aware(event.fetched_at)==fetched_at and event.import_version==5)):continue
        if not event:
            event=Event(id=event_id,source_id=stable("source",source_name),external_id=str(raw["id"]));s.add(event);existing[event_id]=event
        age=str(raw.get("age_restriction")) if raw.get("age_restriction") is not None else "";age_match=re.fullmatch(r"\s*(\d{1,2})\s*\+?\s*",age)
        event.title=clean(raw["title"]);event.description=clean(raw.get("description"));event.category_id=stable("category",slug)
        event.external_url=raw["site_url"];event.age_limit=int(age_match[1]) if age_match else None
        event.kind=raw.get("kind","event");event.schedule_note=raw.get("schedule_note");event.import_version=5
        event.image_url=(raw.get("images") or [{}])[0].get("image")
        event.fetched_at=fetched_at;event.last_seen_at=fetched_at;event.is_demo=False
        # publication_date is not an update timestamp; do not present it as one.
        event.source_updated_at=None
        s.flush()
        place=raw.get("place") if isinstance(raw.get("place"),dict) else {}
        if place and place.get("id") and place.get("title"):
            oid=stable("kudago-place" if source_name=="KudaGo" else "source-place/"+source_name,place["id"])
            org=orgs.get(oid) or by_url.get(place.get("site_url"))
            if not org:
                org=Organizer(id=oid,name=clean(place["title"]),external_url=place.get("site_url"),description="Площадка / организатор из "+source_name);s.add(org);s.flush();orgs[oid]=org
                if org.external_url:by_url[org.external_url]=org
            oid=org.id
            if (event_id,oid) not in org_links:s.add(EventOrganizer(event_id=event_id,organizer_id=oid));org_links.add((event_id,oid))
        tags=title+" "+event.description.casefold().replace("ё","е")
        genres={key for key,pattern in GENRE_PATTERNS.items() if re.search(pattern,tags)} | set(raw.get("genres",[]))
        if slug=="stand-up":genres.add("standup")
        if slug in CATEGORY_GENRES:genres.add(CATEGORY_GENRES[slug])
        for genre in genres:
            gid=stable("interest-category",genre)
            if gid in known_genres and (event_id,gid) not in genre_links:
                s.add(EventInterestCategory(event_id=event_id,category_id=gid));genre_links.add((event_id,gid))
        # Remove obsolete source-inferred genres when the source changes its description.
        desired={stable("interest-category",g) for g in genres}
        for eid,gid in list(genre_links):
            if eid==event_id and gid not in desired:
                s.execute(delete(EventInterestCategory).where(EventInterestCategory.event_id==eid,EventInterestCategory.category_id==gid));genre_links.discard((eid,gid))
        seen=[]
        for d in ([{"start":1,"schedule_kind":"place"}] if event.kind=="place" else raw.get("dates",[])):
            start,end=d.get("start"),d.get("end")
            if not isinstance(start,(float,int)) or isinstance(start,bool) or start<=0:continue
            try:
                begin=datetime.fromtimestamp(start,timezone.utc);finish=datetime.fromtimestamp(end,timezone.utc) if isinstance(end,(int,float)) else None
            except (ValueError,OverflowError,OSError):continue
            if finish and finish<begin:finish=None
            ident=stable("occurrence" if source_name=="KudaGo" else "source-occurrence/"+source_name,f"{raw['id']}/{city_slug}/{start}");seen.append(ident)
            occ=occurrences.get(ident)
            if event.kind!="place" and not occ and (finish or begin)<now:continue
            if not occ:occ=Occurrence(id=ident,event_id=event_id,city_id=stable("city",city_slug),starts_at=begin);s.add(occ);occurrences[ident]=occ;per_event.setdefault(event_id,[]).append(occ)
            occ.schedule_kind=d.get("schedule_kind") or ("period" if finish and (finish-begin).total_seconds()>=86400 else "session")
            occ.external_url=d.get('source_url') or raw['site_url']
            occ.source_available=True;occ.ends_at=finish;occ.venue=clean(place.get("title")) or None;occ.address=clean(place.get("address")) or None
            session_free=d.get("is_free",raw.get("is_free")) is True
            session_price=d.get("price",raw.get("price"));session_low,session_high,session_free=normalize_price(session_price,session_free)
            occ.price_text=clean(session_price) or None;occ.price_min=session_low;occ.price_max=session_high;occ.is_free=session_free
            occ.status="ACTIVE" if event.kind=="place" or (finish or begin)>=now else "FINISHED"
        # Missing sessions in a successfully refreshed item are no longer active.
        for occ in per_event.get(event_id,[]):
            if occ.id not in seen:occ.source_available=False
        n+=1
    source=s.get(EventSource,stable("source",source_name));source.last_sync_at=max(aware(source.last_sync_at),fetched_at) if source.last_sync_at else fetched_at
    return n

def load_snapshot(s,path):
    data=json.loads(Path(path).read_text());fetched=datetime.fromisoformat(data["fetched_at"])
    count=0
    for city,group in data['cities'].items():
        if city not in {'msk','krd'}:continue
        count+=import_items(s,group['results'],city,fetched)
        if group.get('complete'):mark_missing(s,'KudaGo',city,group['results'],fetched)
    return count

def fetch_city(base,city,max_pages=50):
    results=[];complete=False
    params={"lang":"ru","location":city,"page_size":100,"actual_since":int(utcnow().timestamp()),"expand":"place","text_format":"text","fields":"id,title,description,dates,place,location,categories,age_restriction,price,is_free,images,site_url,publication_date"}
    with httpx.Client(timeout=20,follow_redirects=True) as client:
        for page in range(1,max_pages+1):
            r=client.get(base.rstrip('/')+'/events/',params={**params,"page":page});r.raise_for_status();data=r.json();results.extend(data["results"])
            if not data.get("next"):complete=True;break
    return results,complete


def load_venues_snapshot(s,path):
    data=json.loads(Path(path).read_text());fetched=datetime.fromisoformat(data['fetched_at']);count=0
    for source,group in data['sources'].items():
        for city in ('msk','krd'):
            rows=[v for v in group['results'] if v['city']==city]
            if rows:
                count+=import_items(s,rows,city,fetched,source)
                if group.get("complete"):mark_missing(s,source,city,rows,fetched)
    return count


def mark_missing(s,source,city,rows,fetched,kind="event"):
    ids={event_key(source,row['id']) for row in rows}
    for occurrence in s.scalars(select(Occurrence).join(Event).where(Occurrence.city_id==stable('city',city),Event.source_id==stable('source',source),Event.kind==kind,Event.fetched_at<=fetched)):
        if occurrence.event_id not in ids:occurrence.source_available=False


def load_extended_snapshot(s,path):
    data=json.loads(Path(path).read_text());count=0
    for group in data['groups']:
        fetched=datetime.fromisoformat(group['fetched_at'])
        group={**group,'results':[normalize_schedule(r) for r in group['results']]}
        count+=import_items(s,group['results'],group['city'],fetched,group['source'])
        if group.get('complete'):
            for kind in {r.get('kind','event') for r in group['results']}:
                rows=[r for r in group['results'] if r.get('kind','event')==kind]
                mark_missing(s,group['source'],group['city'],rows,fetched,kind)
    return count
