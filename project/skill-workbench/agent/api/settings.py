"""Settings endpoint: disclose capability state, enable with risk acknowledgment."""
from __future__ import annotations

import json

from agent.config.defaults import CAPABILITIES, RISK_ACK_VERSION
from agent.config.runtime import enable, snapshot
from agent.http.errors import DomainError


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def get_settings(params, body, request_id):
    return {
        "capabilities": snapshot(),
        "risk_ack_version": RISK_ACK_VERSION,
    }


def enable_capability(params, body, request_id):
    capability_id = str(params.get("id", ""))
    if capability_id not in CAPABILITIES:
        raise DomainError("E_NOT_FOUND", "wb.error.not_found",
                          params={"id": capability_id}, fix_key="wb.fix.check_path")
    payload = _body(body)
    risk_ack = str(payload.get("risk_ack", ""))
    enabled_by = str(payload.get("enabled_by", "user"))
    if risk_ack != RISK_ACK_VERSION:
        raise DomainError("E_RISK_ACK_REQUIRED", "wb.error.risk_ack_required",
                          params={"capability": capability_id}, fix_key="wb.fix.confirm_risk")
    return enable(capability_id, risk_ack, enabled_by)
