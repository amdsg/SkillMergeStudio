"""Diagnostics export: request_id timeline, redacted, bounded to 5MB."""
from __future__ import annotations

import json

from agent.core.audit import timeline
from agent.http.errors import DomainError

MAX_BYTES = 5 * 1024 * 1024


def get_diagnostics(params, body, request_id):
    target = str(params.get("id", ""))
    events = timeline(target)
    if not events:
        raise DomainError("E_NOT_FOUND", "wb.error.not_found", status=404,
                          params={"request_id": target}, fix_key="wb.fix.check_path")
    payload = {"request_id": target, "events": events, "event_count": len(events)}
    text = json.dumps(payload, ensure_ascii=False)
    if len(text.encode("utf-8")) > MAX_BYTES:
        payload["events"] = payload["events"][:1000]
        payload["truncated"] = True
        payload["event_count"] = len(payload["events"])
        text = json.dumps(payload, ensure_ascii=False)
    payload["bytes"] = len(text.encode("utf-8"))
    return payload