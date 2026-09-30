import asyncio
import re
import time
from urllib.parse import urlparse
import httpx

class MaxAPIError(Exception):
    def __init__(self, status: int, retry_after: float = 30):
        self.status, self.retry_after = status, retry_after
        super().__init__(f"MAX request failed: status={status}")

class MaxClient:
    """Serialize calls and cap requests at 1.8 rps.
    No automatic retry of POST: delivery can be ambiguous after network timeout.
    """
    def __init__(self, client: httpx.AsyncClient, token: str):
        self.client, self.token = client, token
        self._lock, self._last = asyncio.Lock(), 0.0

    async def request(self, method: str, path: str, **kwargs):
        if not self.token: raise MaxAPIError(503)
        async with self._lock:
            await asyncio.sleep(max(0, 0.56 - (time.monotonic() - self._last)))
            self._last = time.monotonic()
            response = await self.client.request(method, "https://platform-api2.max.ru" + path,
                headers={"Authorization": self.token}, timeout=10, **kwargs)
        if response.is_error:
            try: delay = max(1, min(3600, float(response.headers.get("Retry-After", "30"))))
            except ValueError: delay = 30
            raise MaxAPIError(response.status_code, delay)
        try: data = response.json()
        except ValueError: raise MaxAPIError(502) from None
        if not isinstance(data, dict) or data.get("success") is False:
            raise MaxAPIError(400)
        return data

    async def me(self): return await self.request("GET", "/me")
    async def subscriptions(self): return await self.request("GET", "/subscriptions")
    async def subscribe(self, url: str, secret: str):
        u = urlparse(url)
        if u.scheme != "https" or not u.hostname or u.port not in (None, 443) or u.username or u.password:
            raise ValueError("Public webhook must use HTTPS port 443")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{5,256}", secret): raise ValueError("invalid webhook secret")
        return await self.request("POST", "/subscriptions", json={"url": url, "secret": secret,
            "update_types": ["bot_started", "message_created"]})
    async def send(self, text: str, *, user_id: str | None = None, chat_id: str | None = None):
        if bool(user_id) == bool(chat_id): raise ValueError("exactly one recipient is required")
        recipient = user_id or chat_id
        if not re.fullmatch(r"-?\d+", recipient or "") or not 1 <= len(text) <= 4000:
            raise ValueError("invalid recipient or text")
        return await self.request("POST", "/messages", params={"user_id" if user_id else "chat_id": recipient}, json={"text": text})
