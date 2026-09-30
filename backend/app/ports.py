"""Shared interfaces implemented by services.stores against normalized SQLAlchemy models."""
from dataclasses import dataclass, field
from typing import Protocol, Any
from fastapi import APIRouter
from app.auth.validation import VerifiedUser

@dataclass(frozen=True)
class Job:
    id: str
    lease_token: str
    kind: str
    payload: dict[str, Any]
    attempts: int

class UserStore(Protocol):
    async def upsert_max_user(self, user: VerifiedUser) -> dict: ...

class JobStore(Protocol):
    async def enqueue_webhook(self, dedupe_key: str, payload: dict) -> bool: ...
    async def claim(self, lease_seconds: int) -> Job | None: ...
    async def complete(self, job: Job) -> None: ...
    async def retry(self, job: Job, delay_seconds: float, error_code: str) -> None: ...
    async def fail(self, job: Job, error_code: str) -> None: ...
    async def review(self, job: Job, error_code: str) -> None: ...
    async def purge_expired_payloads(self) -> None: ...

class BotStore(Protocol):
    async def notification(self, job: Job) -> dict | None: ...

@dataclass
class Bindings:
    users: UserStore | None = None
    jobs: JobStore | None = None
    bot: BotStore | None = None
    # Each router includes its relative /events etc; main adds /api/v1.
    routers: list[APIRouter] = field(default_factory=list)
    engine: Any = None
    sessions: Any = None

def load_bindings(factory_path: str, settings) -> Bindings:
    if not factory_path: return Bindings()
    import importlib
    module, name = factory_path.split(":", 1)
    bindings = getattr(importlib.import_module(module), name)(settings)
    if not isinstance(bindings, Bindings): raise TypeError("factory must return Bindings")
    return bindings
