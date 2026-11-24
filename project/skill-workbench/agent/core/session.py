"""In-memory bearer sessions: 8h TTL, never persisted."""
from __future__ import annotations

import secrets
import time

SESSION_TTL_SECONDS = 8 * 3600


class SessionStore:
    def __init__(self, ttl: int = SESSION_TTL_SECONDS, clock=time.time) -> None:
        self._ttl = int(ttl)
        self._clock = clock
        self._sessions: dict[str, float] = {}

    def issue(self) -> dict:
        token = secrets.token_urlsafe(32)
        expires_at = self._clock() + self._ttl
        self._sessions[token] = expires_at
        return {"token": token, "expires_at": expires_at, "ttl_seconds": self._ttl}

    def validate(self, token: str) -> bool:
        expires_at = self._sessions.get(str(token or ""))
        if expires_at is None:
            return False
        if self._clock() > expires_at:
            self._sessions.pop(token, None)
            return False
        return True

    def revoke(self, token: str) -> None:
        self._sessions.pop(str(token or ""), None)