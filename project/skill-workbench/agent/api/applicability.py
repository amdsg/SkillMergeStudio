"""Applicability resolution endpoint. Registered fields only."""
from __future__ import annotations

import json

from agent.core.applicability import ack_id, load_registry, resolve


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def resolve_endpoint(params, body, request_id):
    payload = _body(body)
    declaration = payload.get("declaration")
    registered = load_registry()
    result = resolve(declaration if isinstance(declaration, dict) else None, registered)
    result["target_id"] = str(payload.get("target_id", ""))
    result["reason_key"] = f"wb.reason.{result['reason_code']}"
    return result


def ack_endpoint(params, body, request_id):
    payload = _body(body)
    plan_hash = str(payload.get("plan_hash", ""))
    declared = [str(item) for item in payload.get("declared_targets") or []]
    current = str(payload.get("current_target", ""))
    return {"ack_id": ack_id(plan_hash, declared, current), "plan_hash": plan_hash}