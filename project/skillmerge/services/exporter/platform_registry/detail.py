from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

from .format import format_info


def _stale_days(entry) -> Optional[int]:
    value = entry.last_verified_at or entry.verified_at
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None
    today = datetime.now(timezone.utc).date()
    return max(0, (today - parsed).days)


def _limits(entry) -> Optional[Dict[str, Any]]:
    body = entry.rule_body
    if not body:
        return None
    return {
        "name_max_length": body["name"]["max_length"],
        "description_max_chars": body["description"]["max_chars"],
        "bundle_max_mb": body["bundle"]["max_mb"],
        "bundle_max_files": body["bundle"]["max_files"],
        "package_type": body["package"]["type"],
    }


def _platform(entry) -> Dict[str, Any]:
    rule = entry.as_rule()
    return {
        "id": entry.id,
        "label": entry.label,
        "kind": entry.kind,
        "group": entry.group,
        "origin": entry.origin,
        "batch": entry.batch,
        "source": entry.source,
        "source_type": entry.source_type,
        "verification_status": entry.verification_status,
        "evidence_level": entry.evidence_level,
        "verified_at": entry.verified_at,
        "last_verified_at": entry.last_verified_at,
        "unknown_fields": list(entry.unknown_fields),
        "notes": entry.notes,
        "aliases": list(entry.aliases),
        "legacy_limits": entry.legacy_limits,
        "legacy_limits_present": entry.legacy_limits is not None,
        "limits": _limits(entry),
        "is_selectable": True,
        "requires_confirm": entry.verification_status == "unknown",
        "stale_days": _stale_days(entry),
        "rule": rule,
        "format": format_info(entry),
    }


def _verification(directory: str, platform_id: str) -> Dict[str, Any]:
    path = os.path.join(directory, "verification", f"{platform_id}.jsonl")
    if not os.path.isfile(path):
        return {"latest": None, "history": []}
    records = []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    except (OSError, ValueError):
        return {"latest": None, "history": []}
    records.sort(key=lambda item: str(item.get("checked_at", "")), reverse=True)
    return {"latest": records[0] if records else None, "history": records[:20]}


def _record_matches(entry, record: Dict[str, Any]) -> bool:
    key = str(record.get("key", ""))
    url = str(record.get("url", ""))
    final = str(record.get("final_url", ""))
    candidates = {entry.id, *entry.aliases}
    if entry.source:
        candidates.add(str(entry.source))
    return key in candidates or url in candidates or final in candidates


def evidence_pages(entry, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pages = []
    for record in records:
        if not _record_matches(entry, record):
            continue
        key = str(record.get("key", ""))
        pages.append(
            {
                "key": key,
                "label": record.get("label", ""),
                "url": record.get("url", ""),
                "final_url": record.get("final_url", ""),
                "status": record.get("status"),
                "error": record.get("error", ""),
                "markers": record.get("markers", {}),
                "evidence_level": record.get("evidence_level", ""),
                "match": "key" if key in {entry.id, *entry.aliases} else "url",
            }
        )
    return pages


def _domain(url: Optional[str]) -> str:
    if not url:
        return ""
    try:
        return (urlsplit(str(url)).hostname or "").lower()
    except ValueError:
        return ""


def related(registry, entry) -> List[Dict[str, str]]:
    result = []
    for other in registry.entries():
        if other.id == entry.id:
            continue
        if entry.id in other.aliases:
            result.append({"id": other.id, "label": other.label, "relation": "alias"})
        elif other.group == entry.group and _domain(other.source) == _domain(entry.source) and _domain(entry.source):
            result.append({"id": other.id, "label": other.label, "relation": "same_vendor"})
    return sorted(result, key=lambda item: (item["relation"], item["id"]))


def build_detail(registry, platform_id: str, records: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    entry = registry.entry(platform_id)
    if entry is None:
        return None
    return {
        "platform": _platform(entry),
        "verification": _verification(registry.directory, entry.id),
        "evidence_pages": evidence_pages(entry, records),
        "related": related(registry, entry),
    }