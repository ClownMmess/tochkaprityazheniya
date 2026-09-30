"""Dedicated catalogue service: first refresh after startup, then every six hours."""
import logging
import signal
import threading
from app.config import Settings
from app.db.base import make_engine
from sqlalchemy.orm import sessionmaker
from app.integrations.sources.refresh import refresh_all


def run(sessions, settings, stop, refresh=refresh_all):
    if not settings.catalog_refresh_enabled:
        stop.wait()
        return
    while not stop.is_set():
        try: refresh(sessions, settings.kudago_api_url)
        except Exception:
            logging.exception('Catalogue refresh interrupted')
        stop.wait(settings.catalog_refresh_seconds)


def main():
    settings=Settings();engine=make_engine(settings.database_url)
    sessions=sessionmaker(engine,expire_on_commit=False);stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    try:run(sessions,settings,stop)
    finally:engine.dispose()

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    main()
