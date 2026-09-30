from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, Index, ForeignKeyConstraint, JSON, Uuid, Float
from app.db.base import Base, uid, utcnow
U=Uuid(as_uuid=False)
def pk(): return Column(U,primary_key=True,default=uid)
def fk(table,**kw): return Column(U,ForeignKey(table+".id",ondelete=kw.pop("ondelete","CASCADE")),**kw)
def timestamp(**kw): return Column(DateTime(timezone=True),**kw)

class User(Base):
    __tablename__="users"
    id=pk();max_user_id=Column(String(64),unique=True,nullable=False);username=Column(String(128));first_name=Column(String(256),nullable=False);last_name=Column(String(256));avatar_url=Column(Text);created_at=timestamp(default=utcnow,nullable=False)
class AgeGroup(Base):
    __tablename__="age_groups"
    id=pk();name=Column(String(80),nullable=False);slug=Column(String(32),unique=True,nullable=False)
class UserPreference(Base):
    __tablename__="user_preferences"
    id=pk();user_id=fk("users",unique=True,nullable=False);age_group_id=fk("age_groups",nullable=False,ondelete="RESTRICT");budget_min=Column(Integer);budget_max=Column(Integer)
    home_city=Column(String(16));include_nearby=Column(Boolean,nullable=False,default=False,server_default='false')
    __table_args__=(CheckConstraint("budget_min IS NULL OR budget_min >= 0"),CheckConstraint("budget_max IS NULL OR budget_max >= 0"),CheckConstraint("budget_min IS NULL OR budget_max IS NULL OR budget_min <= budget_max"))
class Interest(Base):
    __tablename__="interests"
    id=pk();name=Column(String(120),nullable=False);slug=Column(String(80),unique=True,nullable=False);description=Column(Text)
class InterestCategory(Base):
    __tablename__="interest_categories"
    id=pk();interest_id=fk("interests",nullable=False);name=Column(String(120),nullable=False);slug=Column(String(80),unique=True,nullable=False);description=Column(Text)
class UserInterest(Base):
    __tablename__="user_interests"
    user_id=fk("users",primary_key=True);interest_id=fk("interests",primary_key=True)
class UserInterestCategory(Base):
    __tablename__="user_interest_categories"
    user_id=fk("users",primary_key=True);category_id=fk("interest_categories",primary_key=True)
class Organizer(Base):
    __tablename__="organizers"
    id=pk();name=Column(String(300),nullable=False);description=Column(Text);logo_url=Column(Text);external_url=Column(Text,unique=True);contact_info=Column(Text)
class UserOrganizer(Base):
    __tablename__="user_organizers"
    user_id=fk("users",primary_key=True);organizer_id=fk("organizers",primary_key=True)
class EventSource(Base):
    __tablename__="event_sources"
    id=pk();name=Column(String(100),unique=True,nullable=False);base_url=Column(Text,nullable=False);last_sync_at=timestamp();is_active=Column(Boolean,default=True,nullable=False)
class Category(Base):
    __tablename__="categories"
    id=pk();name=Column(String(120),nullable=False);slug=Column(String(80),unique=True,nullable=False);icon=Column(String(40));interest_id=fk("interests",ondelete="SET NULL")
class City(Base):
    __tablename__="cities"
    id=pk();name=Column(String(100),nullable=False);slug=Column(String(16),unique=True,nullable=False);region=Column(String(100));country=Column(String(100))
class Event(Base):
    __tablename__="events"
    id=pk();source_id=fk("event_sources",nullable=False,ondelete="RESTRICT");category_id=fk("categories",nullable=False,ondelete="RESTRICT",index=True)
    title=Column(String(600),nullable=False);description=Column(Text);image_url=Column(Text);age_limit=Column(Integer);external_url=Column(Text,nullable=False)
    kind=Column(String(16),nullable=False,default='event',server_default='event')
    schedule_note=Column(Text)
    import_version=Column(Integer,nullable=False,default=0,server_default='0')
    # Technical provenance required for idempotent import; no schedule/price/venue here.
    external_id=Column(String(80),nullable=False);source_updated_at=timestamp();fetched_at=timestamp(nullable=False);last_seen_at=timestamp(nullable=False);is_demo=Column(Boolean,default=False,nullable=False)
    __table_args__=(UniqueConstraint("source_id","external_id"),CheckConstraint("age_limit IS NULL OR (age_limit >= 0 AND age_limit <= 100)"))
class EventOrganizer(Base):
    __tablename__="event_organizers"
    event_id=fk("events",primary_key=True);organizer_id=fk("organizers",primary_key=True)
class EventInterestCategory(Base):
    __tablename__="event_interest_categories"
    event_id=fk("events",primary_key=True);category_id=fk("interest_categories",primary_key=True)
class Occurrence(Base):
    __tablename__="event_occurrences"
    id=pk();event_id=fk("events",nullable=False,index=True);starts_at=timestamp(nullable=False,index=True);ends_at=timestamp();city_id=fk("cities",nullable=False,ondelete="RESTRICT",index=True)
    venue=Column(String(500));address=Column(Text);price_min=Column(Integer,index=True);price_max=Column(Integer);price_text=Column(Text);is_free=Column(Boolean,default=False,nullable=False);status=Column(String(16),default="ACTIVE",nullable=False);source_available=Column(Boolean,default=True,nullable=False)
    schedule_kind=Column(String(16),nullable=False,default='session',server_default='session')
    external_url=Column(Text)
    __table_args__=(UniqueConstraint("event_id","city_id","starts_at"),CheckConstraint("status IN ('ACTIVE','CANCELLED','POSTPONED','FINISHED')"),CheckConstraint("price_min IS NULL OR price_min >= 0"),CheckConstraint("price_max IS NULL OR price_max >= 0"),CheckConstraint("price_min IS NULL OR price_max IS NULL OR price_min <= price_max"),CheckConstraint("ends_at IS NULL OR ends_at >= starts_at"),Index("ix_occurrence_city_time","city_id","starts_at"))
class TrackedEvent(Base):
    __tablename__="tracked_events"
    id=pk();user_id=fk("users",nullable=False);occurrence_id=fk("event_occurrences",nullable=False);remind_at=timestamp();is_notified=Column(Boolean,default=False,nullable=False);status=Column(String(16),default="active",nullable=False)
    __table_args__=(UniqueConstraint("user_id","occurrence_id"),CheckConstraint("status IN ('active','cancelled')"))
class QueueMixin:
    status=Column(String(20),default="pending",nullable=False,index=True)
    attempts=Column(Integer,default=0,nullable=False)
    lease_token=Column(String(36));locked_until=timestamp();last_error_code=Column(String(64))
class NotificationJob(QueueMixin,Base):
    __tablename__="notification_jobs"
    id=pk();user_id=fk("users",nullable=False);occurrence_id=fk("event_occurrences",nullable=False);tracking_id=fk("tracked_events",nullable=False)
    type=Column(String(40),nullable=False);scheduled_at=timestamp(nullable=False,index=True);created_at=timestamp(default=utcnow,nullable=False);dedupe_key=Column(String(200),unique=True,nullable=False)
class Job(QueueMixin,Base):
    __tablename__="jobs"
    id=pk();dedupe_key=Column(String(64),unique=True,nullable=False);kind=Column(String(40),nullable=False);payload=Column(JSON,nullable=False,default=dict);run_at=timestamp(default=utcnow,nullable=False,index=True);payload_expires_at=timestamp(nullable=False);created_at=timestamp(default=utcnow,nullable=False)
class GroupChoice(Base):
    __tablename__="group_choices"
    id=pk();creator_id=fk("users",nullable=False);title=Column(String(200),nullable=False);description=Column(Text);public_token=Column(String(100),unique=True,nullable=False);expires_at=timestamp(nullable=False);status=Column(String(16),default="active",nullable=False);created_at=timestamp(default=utcnow,nullable=False)
class GroupChoiceEvent(Base):
    __tablename__="group_choice_events"
    choice_id=fk("group_choices",primary_key=True);occurrence_id=fk("event_occurrences",primary_key=True);recommendation_score=Column(Integer,default=0,nullable=False)
class GroupChoiceVote(Base):
    __tablename__="group_choice_votes"
    id=pk();choice_id=fk("group_choices",nullable=False);occurrence_id=Column(U,nullable=False);user_id=fk("users",nullable=False);created_at=timestamp(default=utcnow,nullable=False)
    __table_args__=(UniqueConstraint("choice_id","user_id","occurrence_id",name="uq_group_vote_option"),ForeignKeyConstraint(["choice_id","occurrence_id"],["group_choice_events.choice_id","group_choice_events.occurrence_id"],ondelete="CASCADE"))
class EventChat(Base):
    __tablename__="event_chats"
    id=pk();event_id=fk("events",nullable=False);max_chat_id=Column(String(64),unique=True,nullable=False);invite_link=Column(Text,nullable=False);is_active=Column(Boolean,default=True,nullable=False)
class ImportRun(Base):
    __tablename__="import_runs"
    id=pk();source_id=fk("event_sources",nullable=False);city_id=fk("cities",nullable=False);started_at=timestamp(default=utcnow,nullable=False);finished_at=timestamp();status=Column(String(20),nullable=False);imported=Column(Integer,default=0,nullable=False);error_code=Column(String(80))
