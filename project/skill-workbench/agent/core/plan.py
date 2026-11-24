"""Dry-run install plan: six information groups, zero writes."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from agent.core.applicability import ack_id, requires_ack
from agent.core.paths import redact_path

PLAN_TTL_SECONDS = 600


def plan_hash(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def preview(files: list[str], target_tool: str, target_path: str, backup_root: str,
            applicability: dict | None, current_target: str, ack: str = "") -> dict:
    normalized_path = redact_path(target_path)
    actions = [{"action": "write", "file": name} for name in files]
    core = {
        "target_tool": target_tool,
        "target_path": normalized_path,
        "files": files,
        "actions": actions,
        "backup_location": backup_root,
    }
    digest = plan_hash(core)
    warnings = []
    if applicability is not None and requires_ack(applicability, current_target):
        expected = ack_id(digest, applicability.get("targets") or [], current_target)
        warnings.append({
            "code": "applicability_mismatch",
            "declared_targets": applicability.get("targets") or [],
            "current_target": current_target,
            "ack_required": True,
            "ack_id": expected,
        })
        if ack != expected:
            return {
                "dry_run": True,
                "plan_hash": digest,
                "warnings": warnings,
                "ack_required": True,
                "writes": 0,
            }
    return {
        "dry_run": True,
        "target_tool": target_tool,
        "target_path": normalized_path,
        "files": files,
        "diffs": [{"file": name, "change": "add"} for name in files],
        "backup_location": backup_root,
        "actions": actions,
        "plan_hash": digest,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=PLAN_TTL_SECONDS)).isoformat(),
        "warnings": warnings,
        "writes": 0,
    }