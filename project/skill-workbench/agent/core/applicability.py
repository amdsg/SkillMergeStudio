"""Applicability declaration: universal / model_specific / unknown.

Only registered fields are parsed. Repository metadata is never used as evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APPLICABILITY = ROOT / "agent" / "adapters" / "applicability.json"

UNIVERSAL = "universal"
MODEL_SPECIFIC = "model_specific"
UNKNOWN = "unknown"
STATES = (UNIVERSAL, MODEL_SPECIFIC, UNKNOWN)
ACK_ERROR = "E_APPLICABILITY_ACK_REQUIRED"


def load_registry() -> dict:
    try:
        data = json.loads(APPLICABILITY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {
        "source_files": list(data.get("source_files") or []),
        "field_names": list(data.get("field_names") or []),
    }


def resolve(declaration: dict | None, registered: dict | None = None) -> dict:
    if declaration is None:
        return {"mode": UNKNOWN, "targets": [], "reason_code": "not_fetched", "invalid_targets": []}
    fields = declaration.get("fields") or {}
    source_file = str(declaration.get("source_file", ""))
    registry = registered or load_registry()
    if source_file and source_file not in registry["source_files"]:
        return {"mode": UNKNOWN, "targets": [], "reason_code": "field_unregistered", "invalid_targets": []}
    declared = []
    for name in registry["field_names"]:
        value = fields.get(name)
        if isinstance(value, str) and value.strip():
            declared.extend(part.strip() for part in value.replace(";", ",").split(",") if part.strip())
        elif isinstance(value, list):
            declared.extend(str(part).strip() for part in value if str(part).strip())
    if not declared:
        return {"mode": UNKNOWN, "targets": [], "reason_code": "not_declared", "invalid_targets": []}
    normalized = sorted({item.lower() for item in declared})
    if normalized == ["*"] or normalized == ["universal"]:
        return {"mode": UNIVERSAL, "targets": [], "reason_code": "declared_universal", "invalid_targets": []}
    return {"mode": MODEL_SPECIFIC, "targets": normalized, "reason_code": "declared_targets", "invalid_targets": []}


def ack_id(plan_hash: str, declared: list[str], current: str) -> str:
    payload = "|".join([plan_hash, ",".join(sorted(declared)), current])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def requires_ack(applicability: dict, current_target: str) -> bool:
    if applicability.get("mode") != MODEL_SPECIFIC:
        return False
    return current_target not in (applicability.get("targets") or [])