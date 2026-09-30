from datetime import date
from typing import Literal
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,model_validator
from app.integrations.llm.schemas import SearchIntent
from app.services.locations import CityCode

class StrictModel(BaseModel):model_config=ConfigDict(extra="forbid")
class PreferencesIn(StrictModel):
    home_city:CityCode='msk'
    include_nearby:bool=False
    age_group_id:UUID
    interest_ids:list[UUID]=Field(default_factory=list,max_length=30)
    interest_category_ids:list[UUID]=Field(default_factory=list,max_length=100)
    organizer_ids:list[UUID]=Field(default_factory=list,max_length=100)
    budget_min:int|None=Field(default=None,ge=0)
    budget_max:int|None=Field(default=None,ge=0)
    @model_validator(mode="after")
    def valid_budget(self):
        if self.budget_min is not None and self.budget_max is not None and self.budget_min>self.budget_max:raise ValueError("Неверный диапазон бюджета")
        return self
class TrackIn(StrictModel):remind_before_minutes:int=Field(default=1440,ge=1,le=43200)
class ChoiceIn(StrictModel):
    title:str=Field(min_length=1,max_length=200)
    description:str|None=Field(default=None,max_length=1000)
    occurrence_ids:list[UUID]=Field(min_length=2,max_length=5)
class VoteIn(StrictModel):occurrence_id:UUID
class NaturalIn(StrictModel):
    text:str=Field(min_length=1,max_length=2000)
    city:CityCode
    include_nearby:bool=False
    context:SearchIntent|None=None

class PreviewIn(NaturalIn):
    text:str=Field(min_length=0,max_length=2000)
