"""Pairing endpoints. Tokens stay in process memory; pair.txt holds only the code."""
from __future__ import annotations

import json

from agent.core.pairing import PairingStore
from agent.core.paths import store_dir
from agent.core.session import SessionStore
from agent.http.errors import DomainError

PAIRING_ENABLED = False
_store = PairingStore(store_dir())
_sessions = SessionStore()


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def create_code(params, body, request_id):
    if not PAIRING_ENABLED:
        raise DomainError("E_CAPABILITY_DISABLED", "wb.error.capability_disabled", status=403,
                          params={"capability": "pairing"}, fix_key="wb.fix.enable_capability")
    return _store.create()


def confirm_code(params, body, request_id):
    payload = _body(body)
    _store.consume(str(payload.get("code", "")))
    return _sessions.issue()


def pair_status(params, body, request_id):
    return {
        "pairing_enabled": PAIRING_ENABLED,
        "session_ttl_seconds": 8 * 3600,
        "token_persisted": False,
    }


def require_bearer(headers) -> bool:
    if not PAIRING_ENABLED:
        return True
    value = headers.get("Authorization", "")
    token = value[7:] if value.startswith("Bearer ") else ""
    return _sessions.validate(token)