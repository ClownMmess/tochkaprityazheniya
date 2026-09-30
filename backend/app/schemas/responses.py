"""Public response contracts for the catalogue and group choice API."""
from typing import Any
from pydantic import BaseModel, ConfigDict
from app.integrations.llm.schemas import SearchIntent


class Output(BaseModel):
    model_config = ConfigDict(extra='allow')


class ErrorBody(Output):
    code: str
    message: str
    request_id: str
    details: dict[str, Any]


class ErrorOut(Output):
    error: ErrorBody


class MatchOut(Output):
    percent: int | None
    reasons: list[str]


class SourceOut(Output):
    name: str
    url: str
    fetched_at: str
    updated_at: str | None


class EventOut(Output):
    id: str
    occurrence_id: str
    title: str
    city: str
    city_name: str
    kind: str
    schedule_kind: str
    schedule_note: str | None
    starts_at: str | None
    ends_at: str | None
    place_name: str | None
    address: str | None
    price_min: int | None
    price_max: int | None
    price_text: str | None
    is_free: bool
    age_restriction: int | None
    categories: list[str]
    category_name: str
    image_url: str | None
    status: str
    is_demo: bool
    is_tracked: bool
    remind_at: str | None
    organizers: list[dict[str, Any]]
    genres: list[dict[str, str]]
    available_occurrences: int
    source: SourceOut
    match: MatchOut


class AlternativeOut(Output):
    label: str
    explanation: str
    estimated_count: int
    intent: SearchIntent
    events: list[EventOut]


class EventPageOut(Output):
    items: list[EventOut]
    page: int
    page_size: int
    total: int
    alternatives: list[AlternativeOut] = []


class DetailOut(EventOut):
    description: str
    occurrences: list[EventOut]


class RankedOut(Output):
    event: EventOut
    score: float
    reasons: list[str]


class NaturalOut(Output):
    intent: SearchIntent
    results: list[RankedOut]
    total: int
    page: int
    page_size: int
    llm_status: str
    relaxations: list[AlternativeOut]
    questions: list[dict[str, Any]]


class ChoiceEventOut(Output):
    event: EventOut
    votes: int | None


class ChoiceOut(Output):
    id: str
    title: str
    public_token: str
    deep_link: str | None
    web_link: str
    events: list[ChoiceEventOut]
    my_votes: list[str]
    results_visible: bool
    voter_count: int | None
    total_votes: int | None
    expires_at: str
    status: str


class PreferencesOut(Output):
    home_city: str | None
    include_nearby: bool
    age_group_id: str | None
    interest_ids: list[str]
    interest_category_ids: list[str]
    organizer_ids: list[str]
    budget_min: int | None
    budget_max: int | None


class AuthOut(Output):
    access_token: str
    token_type: str
    expires_in: int
    user: dict[str, Any]


class CommunityOut(Output):
    invite_link: str | None


class HealthOut(Output):
    status: str
    database: str
