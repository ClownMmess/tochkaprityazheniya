import argparse,json,sys
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import select,func
from sqlalchemy.orm import sessionmaker
from app.config import Settings
from app.db.base import make_engine,utcnow
from app.models import *
from app.services.bootstrap import bootstrap,stable
from app.integrations.kudago.importer import load_snapshot,load_venues_snapshot,load_extended_snapshot,fetch_city,import_items


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['init','import-events','register-chat']);p.add_argument('--snapshot',default='seed/kudago_snapshot.json');p.add_argument('--event-id');p.add_argument('--chat-id');p.add_argument('--invite-link');args=p.parse_args()
    settings=Settings();engine=make_engine(settings.database_url);sessions=sessionmaker(engine,expire_on_commit=False)
    if args.command=='init':
        cfg=Config('alembic.ini');cfg.set_main_option('sqlalchemy.url',settings.database_url.replace('%','%%'));command.upgrade(cfg,'head')
        with sessions.begin() as s:
            bootstrap(s)
            path=Path(args.snapshot)
            if path.exists():print('Catalogue snapshot merged:',load_snapshot(s,path))
            else:print('Snapshot missing; run import-events before live demonstration.')
            venues=path.with_name('venues_snapshot.json')
            if venues.exists():print('Official venue snapshots merged:',load_venues_snapshot(s,venues))
            extended=path.with_name('extended_snapshot.json')
            if extended.exists():print('Expanded catalogue merged:',load_extended_snapshot(s,extended))
            additions=path.with_name('local_snapshot.json')
            if additions.exists():print('Local venues and area catalogue merged:',load_extended_snapshot(s,additions))
            updates=path.with_name('updates_snapshot.json')
            if updates.exists():print('Latest catalogue updates merged:',load_extended_snapshot(s,updates))
            from app.services.prices import repair_cached_prices
            repair_cached_prices(s)
        print('Database initialized.')
    elif args.command=='import-events':
        from app.integrations.sources.refresh import refresh_all
        results=refresh_all(sessions,settings.kudago_api_url)
        if any(r['status']=='failed' for r in results):raise SystemExit(1)
    elif args.command=='register-chat':
        from urllib.parse import urlparse
        if not args.event_id or not args.chat_id or not args.invite_link:raise SystemExit('--event-id, --chat-id, --invite-link required')
        u=urlparse(args.invite_link)
        if u.scheme!='https' or u.hostname!='max.ru':raise SystemExit('Use a real HTTPS MAX invite link')
        with sessions.begin() as s:
            if not s.get(Event,args.event_id):raise SystemExit('Unknown event ID')
            row=s.scalar(select(EventChat).where(EventChat.max_chat_id==args.chat_id))
            if not row:row=EventChat(max_chat_id=args.chat_id,event_id=args.event_id,invite_link=args.invite_link);s.add(row)
            row.event_id=args.event_id;row.invite_link=args.invite_link;row.is_active=True
        print('Chat registered. The app now offers the registered link.')
    engine.dispose()
if __name__=='__main__':main()
