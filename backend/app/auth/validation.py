import hashlib
import hmac
import json
import re
import time
from urllib.parse import parse_qsl
from pydantic import BaseModel

class VerifiedUser(BaseModel):
    max_user_id: str
    first_name: str


def verify_init_data(raw: str, token: str, *, now: int | None = None, max_age: int = 3600) -> VerifiedUser:
    """Official MAX HMAC; decode once, preserve raw JSON for signature."""
    try:
        if not token or not raw or len(raw) > 16384 or re.search(r"%(?![0-9a-fA-F]{2})", raw):
            raise ValueError()
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=32)
        if len({k for k, _ in pairs}) != len(pairs):
            raise ValueError()
        data = dict(pairs)
        supplied = data.pop("hash")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", supplied):
            raise ValueError()
        check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
        key = hmac.digest(b"WebAppData", token.encode(), "sha256")
        expected = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied.lower()):
            raise ValueError()
        auth_date = int(data["auth_date"])
        age = (int(time.time()) if now is None else now) - auth_date
        if age < -30 or age > max_age:
            raise ValueError()
        user = json.loads(data["user"])
        uid = user["id"]
        if isinstance(uid, bool) or not isinstance(uid, (int, str)) or not re.fullmatch(r"[0-9]{1,20}", str(uid)):
            raise ValueError()
        name = user.get("first_name", "")
        if not isinstance(name, str) or len(name) > 256:
            raise ValueError()
        return VerifiedUser(max_user_id=str(uid), first_name=name)
    except (KeyError, TypeError, ValueError):
        raise ValueError("invalid_max_init_data") from None
