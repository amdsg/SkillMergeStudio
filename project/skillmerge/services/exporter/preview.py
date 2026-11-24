from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List

from .export_service import ExportOptions


def export_preview(service, artifact, platforms: List[str], options: ExportOptions) -> Dict[str, Any]:
    items = []
    for platform in platforms:
        items.append(service.preview_one(artifact, replace(options, platform=platform)))
    summary = {
        "total": len(items),
        "verified": sum(1 for item in items if item["format"]["rule_status"] == "verified"),
        "candidate": sum(1 for item in items if item["format"]["rule_status"] == "candidate"),
        "installable": sum(1 for item in items if item["install_available"]),
    }
    return {"artifact_id": artifact.id, "items": items, "summary": summary}