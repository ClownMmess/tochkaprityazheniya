from datetime import timedelta
from sqlalchemy import select
from app.models import *
from app.db.base import utcnow
from app.services.bootstrap import stable,bootstrap,CATEGORIES

# Synthetic fixtures are isolated by is_demo and visibly labelled in every screen.
def seed_demo(s):
    bootstrap(s);now=utcnow()
    for i in range(24):
        eid=stable("demo-event",i);oid=stable("demo-occurrence",i)
        if s.get(Event,eid):continue
        category=["theater","concert","exhibition","cinema","stand-up","education","entertainment","festival"][i%8];city="msk" if i%3 else "krd"
        s.add(Event(id=eid,source_id=stable("source","Демонстрационные данные"),category_id=stable("category",category),title=f"Демо · {CATEGORIES[category][0]} — встреча {i+1}",description="Синтетическое событие для проверки функций. Это не настоящее мероприятие и не предложение билетов.",external_url="https://example.invalid/demo",external_id=str(i),age_limit=[0,6,12,16,18][i%5],fetched_at=now,last_seen_at=now,is_demo=True))
        s.flush();start=(now+timedelta(days=1+i%8)).replace(hour=15+(i%4),minute=0,second=0,microsecond=0)
        price=0 if i%4==0 else 300+(i%6)*250
        s.add(Occurrence(id=oid,event_id=eid,starts_at=start,ends_at=start+timedelta(hours=2),city_id=stable("city",city),venue="Тестовая площадка",address="Тестовые данные; реального адреса нет",price_min=price,price_max=price,price_text="Бесплатно" if price==0 else f"{price} ₽",is_free=price==0,status="ACTIVE"))
    s.flush()
