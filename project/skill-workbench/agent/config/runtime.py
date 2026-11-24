"""Runtime capability overrides persisted under the store dir.

``defaults.CAPABILITIES`` stays the immutable source of defaults (all off);
this module layers a disk-backed current value on top so high-risk
capabilities can be enabled explicitly, with audit trail, without touching
the static default (which the ``check_wb_defaults`` gate pins to False).

An override counts as enabled only when it carries a matching ``risk_ack``
and both ``enabled_at`` / ``enabled_by``; an "unverified" override (e.g. a
settings file edited by hand) is surfaced but never takes effect.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent.config.defaults import CAPABILITIES, RISK_ACK_VERSION
from agent.core.paths import STORE_DIR

SETTINGS_PATH = STORE_DIR / "settings.json"


def _load() -> dict:
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save(data: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(SETTINGS_PATH)


def overrides() -> dict:
    caps = _load().get("capabilities") or {}
    if not isinstance(caps, dict):
        return {}
    return {cid: caps.get(cid) for cid in CAPABILITIES if isinstance(caps.get(cid), dict)}


def _verified(override: dict) -> bool:
    return (
        bool(override.get("enabled"))
        and override.get("risk_ack") == RISK_ACK_VERSION
        and bool(override.get("enabled_at"))
        and bool(override.get("enabled_by"))
    )


def is_enabled(capability_id: str) -> bool:
    if capability_id not in CAPABILITIES:
        return False
    return _verified(overrides().get(capability_id, {}))


def snapshot() -> list[dict]:
    caps = overrides()
    result = []
    for cid, default_value in CAPABILITIES.items():
        override = caps.get(cid, {})
        enabled = _verified(override)
        result.append({
            "capability_id": cid,
            "default_value": default_value,
            "enabled": enabled,
            "enabled_at": override.get("enabled_at") if enabled else None,
            "enabled_by": override.get("enabled_by") if enabled else None,
            "risk_ack": override.get("risk_ack") if enabled else None,
            "unverified": bool(override.get("enabled")) and not enabled,
        })
    return result


def enable(capability_id: str, risk_ack: str, enabled_by: str) -> dict:
    if capability_id not in CAPABILITIES:
        raise KeyError(capability_id)
    if risk_ack != RISK_ACK_VERSION:
        raise ValueError("risk_ack_version_mismatch")
    now = datetime.now(timezone.utc).isoformat()
    data = _load()
    caps = data.get("capabilities") or {}
    if not isinstance(caps, dict):
        caps = {}
    caps[capability_id] = {
        "enabled": True,
        "enabled_at": now,
        "enabled_by": str(enabled_by or "user"),
        "risk_ack": risk_ack,
    }
    data["capabilities"] = caps
    _save(data)
    return caps[capability_id]
