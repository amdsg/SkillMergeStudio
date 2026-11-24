"""Append-only in-memory event timeline keyed by request_id (max 5000 events)."""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from agent.core.redact import redact_obj

MAX_EVENTS = 5000
_events: deque = deque(maxlen=MAX_EVENTS)


def record(request_id: str, event: str, fields: dict | None = None) -> dict:
    item = {
        "request_id": str(request_id or ""),
        "event": str(event),
        "at": datetime.now(timezone.utc).isoformat(),
        "fields": redact_obj(fields or {}),
    }
    _events.append(item)
    return item


def timeline(request_id: str) -> list[dict]:
    return [item for item in _events if item["request_id"] == str(request_id or "")]


def clear() -> None:
    _events.clear()


def count() -> int:
    return len(_events)