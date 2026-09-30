from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.services.locations import CityCode

class SearchIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: CityCode
    include_nearby: bool = False
    date_from: date | None = None
    date_to: date | None = None
    time_of_day: Literal["morning", "afternoon", "evening", "night"] | None = None
    party_size: int = Field(default=1, ge=1, le=100)
    budget_total: int | None = Field(default=None, ge=0)
    budget_per_person: int | None = Field(default=None, ge=0)
    categories: list[str] = Field(default_factory=list, max_length=20)
    interest_categories: list[str] = Field(default_factory=list, max_length=20)
    organizers: list[str] = Field(default_factory=list, max_length=20)
    performers: list[str] = Field(default_factory=list, max_length=10)
    excluded_categories: list[str] = Field(default_factory=list, max_length=20)
    age_max: int | None = Field(default=None, ge=0, le=100)
    age_exact: int | None = Field(default=None, ge=0, le=100)
    venue_type: Literal['museum', 'park'] | None = None
    keywords: list[str] = Field(default_factory=list, max_length=10)
    corrected_text: str | None = None
    price_match: Literal['from','strict'] = 'from'
    free_only: bool = False
    hard_constraints: list[Literal["city", "date", "budget", "time", "category", "interest_category", "organizer", "free", "performer", "age", "venue", "keywords"]] = Field(default_factory=list)
    unparsed_terms: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def date_order(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from exceeds date_to")
        return self

