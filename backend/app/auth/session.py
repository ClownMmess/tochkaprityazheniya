import time
from uuid import UUID
import jwt

ISSUER = "max-afisha"
AUDIENCE = "max-afisha-api"
TTL = 3600

def issue_session(user_id: str, secret: str) -> str:
    if len(secret) < 32:
        raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
    UUID(user_id)
    now = int(time.time())
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + TTL,
                       "iss": ISSUER, "aud": AUDIENCE}, secret, algorithm="HS256")

def verify_session(token: str, secret: str) -> str:
    if len(secret) < 32:
        raise ValueError("invalid_session")
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"], issuer=ISSUER,
                            audience=AUDIENCE, options={"require": ["sub", "iat", "exp", "iss", "aud"]})
        return str(UUID(claims["sub"]))
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise ValueError("invalid_session") from None
