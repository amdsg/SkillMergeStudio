"""Target listing and target-to-tool recommendation endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from agent.adapters.loader import ROOT, registry
from agent.core.tool_match import recommend
from agent.http.errors import DomainError

TOOLS_DIR = ROOT / "agent" / "evidence" / "tools"


def _load_tools() -> list[dict]:
    tools = []
    for path in TOOLS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        data.setdefault("state", "unknown")
        data.setdefault("matched_path", "")
        tools.append(data)
    return tools


def list_targets(params, body, request_id):
    items = [
        {
            "id": item.get("id"),
            "label": item.get("label"),
            "kind": item.get("kind"),
            "evidence_level": item.get("evidence_level"),
            "evidence_subtype": item.get("evidence_subtype"),
            "format_family": item.get("format_family"),
            "group": item.get("group"),
            "aliases": item.get("aliases") or [],
            "enabled": item.get("enabled", True),
        }
        for item in registry.items
    ]
    return {
        "items": items,
        "counts": registry.counts,
        "groups": registry.groups,
        "sample_ids": registry.sample_ids(),
        "diagnostics": registry.diagnostics(),
    }


def target_tools(params, body, request_id):
    target_id = str(params.get("id", ""))
    target = registry.get(target_id)
    if target is None:
        raise DomainError("E_TARGET_NOT_REGISTERED", "wb.error.target_not_registered",
                          params={"target": target_id}, fix_key="wb.fix.register_target")
    tools = _load_tools()
    result = recommend(target_id, registry.tool_hints, tools)
    return {
        "target_id": target_id,
        "recommended_tool_id": result["recommended_tool_id"],
        "reason_code": result["reason_code"],
        "candidates": result["candidates"],
        "target_evidence_level": target.get("evidence_level"),
    }