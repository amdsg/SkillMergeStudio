"""Install preview endpoint (dry-run only; real write is a gated capability)."""
from __future__ import annotations

import json

from agent.core.plan import preview
from agent.core.records import append
from agent.http.errors import DomainError


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def preview_endpoint(params, body, request_id):
    payload = _body(body)
    files = [str(name) for name in payload.get("files") or []]
    if not files:
        raise DomainError("E_BAD_REQUEST", "wb.error.bad_request",
                          params={"fields": ["files"]}, fix_key="wb.fix.check_input")
    target_tool = str(payload.get("target_tool", ""))
    target_path = str(payload.get("target_path", ""))
    if not target_tool or not target_path:
        raise DomainError("E_TARGET_UNKNOWN", "wb.error.target_unknown",
                          params={"tool": target_tool}, fix_key="wb.fix.choose_tool")
    if ".." in target_path:
        raise DomainError("E_PATH_DENIED", "wb.error.path_denied",
                          params={"path": target_path}, fix_key="wb.fix.check_path")
    applicability = payload.get("applicability") if isinstance(payload.get("applicability"), dict) else None
    result = preview(
        files=files,
        target_tool=target_tool,
        target_path=target_path,
        backup_root=str(payload.get("backup_root", "backups")),
        applicability=applicability,
        current_target=str(payload.get("current_target", "")),
        ack=str(payload.get("ack_id", "")),
    )
    if not result.get("ack_required"):
        append("installs", {"state": "planned", "plan_hash": result["plan_hash"], "writes": 0})
    return result