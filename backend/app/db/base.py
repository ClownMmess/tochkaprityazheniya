from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

def utcnow(): return datetime.now(timezone.utc)
def uid(): return str(uuid4())
def aware(value): return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
class Base(DeclarativeBase): pass

def make_engine(url):
    opts = {"check_same_thread": False, "timeout": 20} if url.startswith("sqlite") else {"connect_timeout": 5, "prepare_threshold": None}
    engine = create_engine(url, pool_pre_ping=True, connect_args=opts)
    if url.startswith("sqlite"):
        @event.listens_for(engine,"connect")
        def enable_fk(dbapi_conn, _): dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine
