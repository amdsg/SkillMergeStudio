"""Health endpoint: discloses capabilities, evidence counts and blocked state."""
from __future__ import annotations

import json
from pathlib import Path

from agent.config.defaults import RISK_ACK_VERSION
from agent.config.runtime import snapshot

ROOT = Path(__file__).resolve().parents[2]
INHERITANCE = ROOT / "agent/store/records/inheritance.json"
TARGETS = ROOT / "agent/adapters/targets.json"


def _load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def _target_counts() -> dict:
    items = _load(TARGETS, [])
    if not isinstance(items, list):
        return {"total": 0, "verified": 0, "candidate": 0, "unknown": 0, "disabled": 0}
    enabled = [item for item in items if item.get("enabled", True)]
    counts = {"total": len(enabled), "verified": 0, "candidate": 0, "unknown": 0, "disabled": len(items) - len(enabled)}
    for item in enabled:
        level = str(item.get("evidence_level", "unknown"))
        if level in counts:
            counts[level] += 1
    return counts


def _inheritance() -> dict:
    data = _load(INHERITANCE, {})
    if not isinstance(data, dict):
        return {"state": "blocked", "reason_code": "inheritance_source_missing"}
    return data


def health(params, body, request_id):
    inheritance = _inheritance()
    return {
        "api_version": "wb-1",
        "capabilities": snapshot(),
        "risk_ack_version": RISK_ACK_VERSION,
        "evidence": {"targets": _target_counts()},
        "engine": {"state": "missing"},
        "inheritance": {
            "state": str(inheritance.get("state", "blocked")),
            "reason_code": str(inheritance.get("reason_code", "inheritance_source_missing")),
            "path": str(inheritance.get("path", "")),
            "checked_at": str(inheritance.get("checked_at", "")),
        },
        "records": {"merges": 0, "upgrades": 0, "conversions": 0, "installs": 0},
    }