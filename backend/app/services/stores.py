import asyncio,json
from datetime import timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models import User,UserPreference,Job as DBJob,NotificationJob,TrackedEvent,Occurrence,Event
from app.ports import Job
from app.db.base import utcnow,aware
from app.services.catalog import is_actual

def background(fn):
    async def call(self,*a,**kw):return await asyncio.to_thread(fn,self,*a,**kw)
    return call

class Stores:
    def __init__(self,sessions,settings):self.sessions,self.settings=sessions,settings
    @background
    def upsert_max_user(self,verified):
        with self.sessions.begin() as s:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            insert=pg_insert if s.bind.dialect.name=='postgresql' else sqlite_insert
            stmt=insert(User).values(max_user_id=verified.max_user_id,first_name=verified.first_name).on_conflict_do_update(index_elements=[User.max_user_id],set_={'first_name':verified.first_name}).returning(User.id)
            ident=s.scalar(stmt);u=s.get(User,ident)
            from app.api.routes import user_json
            return user_json(s,u)
    @background
    def enqueue_webhook(self,dedupe_key,payload):
        # Only direct /start messages and bot_started updates enter the queue.
        with self.sessions() as s:
            if payload.get('chat_type')!='dialog':return False
            if payload.get('chat_type')=='dialog' and payload.get('update_type')!='bot_started' and payload.get('text','').strip().lower()!='/start':return False
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            insert=pg_insert if s.bind.dialect.name=='postgresql' else sqlite_insert
            stmt=insert(DBJob).values(dedupe_key=dedupe_key,kind='max_update',payload=payload,payload_expires_at=utcnow()+timedelta(minutes=15)).on_conflict_do_nothing(index_elements=[DBJob.dedupe_key]).returning(DBJob.id)
            ident=s.scalar(stmt);s.commit();return ident is not None
    @background
    def claim(self,lease_seconds):
        with self.sessions.begin() as s:
            now=utcnow()
            for model,timecol,prefix in [(NotificationJob,NotificationJob.scheduled_at,'n:'),(DBJob,DBJob.run_at,'w:')]:
                q=select(model).where(model.status=='pending',timecol<=now)
                if model is DBJob:q=q.where(DBJob.payload_expires_at>now)
                row=s.scalar(q.order_by(timecol,model.id).with_for_update(skip_locked=True).limit(1))
                if row:
                    row.status='processing';row.attempts+=1;row.lease_token=str(uuid4());row.locked_until=now+timedelta(seconds=lease_seconds)
                    return Job(prefix+row.id,row.lease_token,row.type if model is NotificationJob else row.kind,{} if model is NotificationJob else dict(row.payload),row.attempts)
        return None
    def _transition(self,job,status,error=None,delay=None):
        model=NotificationJob if job.id.startswith('n:') else DBJob
        with self.sessions.begin() as s:
            row=s.scalar(select(model).where(model.id==job.id[2:],model.lease_token==job.lease_token,model.status=='processing').with_for_update())
            if not row:return
            row.status=status;row.last_error_code=error;row.locked_until=None;row.lease_token=None
            if status=='pending':
                if model is DBJob:row.run_at=utcnow()+timedelta(seconds=delay)
                else:row.scheduled_at=utcnow()+timedelta(seconds=delay)
            elif model is DBJob:row.payload={}
            if status=='done' and model is NotificationJob:
                row.status='preview' if self.settings.demo_mode else 'sent'
                if row.type=='event_reminder':
                    tracking=s.get(TrackedEvent,row.tracking_id)
                    if tracking and tracking.status=='active':tracking.is_notified=True
    @background
    def complete(self,job):self._transition(job,'done')
    @background
    def fail(self,job,error_code):self._transition(job,'failed',error_code)
    @background
    def review(self,job,error_code):self._transition(job,'review',error_code)
    @background
    def retry(self,job,delay_seconds,error_code):self._transition(job,'pending',error_code,delay_seconds)
    @background
    def purge_expired_payloads(self):
        with self.sessions.begin() as s:
            now=utcnow()
            for model in [DBJob,NotificationJob]:
                for row in s.scalars(select(model).where(model.status=='processing',model.locked_until<now).with_for_update(skip_locked=True)):
                    row.status='review';row.last_error_code='lease_expired_delivery_unknown';row.lease_token=None;row.locked_until=None
                    if model is DBJob:row.payload={}
            for row in s.scalars(select(DBJob).where(DBJob.status!='processing',DBJob.payload_expires_at<=now).with_for_update(skip_locked=True)):
                row.payload={}
                if row.status=='pending':row.status='failed';row.last_error_code='payload_expired'
    @background
    def notification(self,job):
        with self.sessions.begin() as s:
            row=s.scalar(select(NotificationJob).where(NotificationJob.id==job.id[2:],NotificationJob.status=='processing',NotificationJob.lease_token==job.lease_token).with_for_update())
            if not row:return None
            track=s.get(TrackedEvent,row.tracking_id);occ=s.get(Occurrence,row.occurrence_id)
            if not track or track.status!='active' or not occ or not is_actual(occ) or (row.type=='event_reminder' and aware(occ.starts_at)<=utcnow()):
                row.status='cancelled';row.last_error_code='no_longer_actual';return None
            event=s.get(Event,occ.event_id);u=s.get(User,row.user_id)
            if not self.settings.demo_mode and (event.is_demo or u.max_user_id.startswith('demo_')):
                row.status='cancelled';row.last_error_code='demo_disabled';return None
            from zoneinfo import ZoneInfo
            url=occ.external_url or event.external_url
            if occ.schedule_kind=='place':
                text=f'Вы сохранили место: {event.title}. '+(event.schedule_note or 'Режим работы уточняйте у площадки.')+' '+url
            else:
                moment=aware(occ.starts_at).astimezone(ZoneInfo('Europe/Moscow')).strftime('%d.%m.%Y %H:%M')
                verb='Вы отслеживаете' if row.type=='tracking_confirmation' else 'Напоминание'
                text=f'{verb}: {event.title}. {moment} (МСК). '+(occ.venue or 'Площадка не указана')+'. '+url
            return {'max_user_id':u.max_user_id,'text':text[:4000]}
