import hashlib
import json
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

class Recipient(BaseModel):
    chat_id: int | str | None = None
    chat_type: str
    @field_validator("chat_id", mode="before")
    @classmethod
    def identifier(cls, value):
        if isinstance(value, bool) or (value is not None and not isinstance(value, (int, str))):
            raise ValueError("invalid id")
        return value

class Sender(BaseModel):
    user_id: int | str
    is_bot: bool = False

class Body(BaseModel):
    mid: str = Field(min_length=1, max_length=256)
    text: str | None = Field(default=None, max_length=12000)

class Message(BaseModel):
    recipient: Recipient
    sender: Sender | None = None
    body: Body | None = None

class MessageUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    update_type: str
    timestamp: int
    message: Message

class StartUpdate(BaseModel):
    update_type: str
    timestamp: int
    chat_id: int | str
    user: Sender


def normalize_update(data: dict) -> tuple[str, dict] | None:
    kind = data.get("update_type")
    if kind == "message_created":
        update = MessageUpdate.model_validate(data)
        m = update.message
        if not m.body or not m.body.text or not m.sender or m.sender.is_bot: return None
        chat_type = m.recipient.chat_type.lower()
        if chat_type != "dialog" or m.body.text.strip().lower() != "/start": return None
        if m.recipient.chat_id is None: raise ValueError("missing chat_id")
        payload = {"update_type": kind, "timestamp": update.timestamp,
                   "chat_type": chat_type, "chat_id": str(m.recipient.chat_id),
                   "user_id": str(m.sender.user_id), "message_id": m.body.mid, "text": m.body.text}
        identity = [kind, payload["chat_id"], m.body.mid]
    elif kind == "bot_started":
        update = StartUpdate.model_validate(data)
        payload = {"update_type": kind, "timestamp": update.timestamp, "chat_type": "dialog",
                   "chat_id": str(update.chat_id), "user_id": str(update.user.user_id)}
        identity = [kind, payload["chat_id"], payload["user_id"], str(update.timestamp)]
    else: return None
    key = hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()
    return key, payload
