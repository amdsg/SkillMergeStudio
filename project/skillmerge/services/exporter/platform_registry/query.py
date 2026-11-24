from __future__ import annotations

import unicodedata
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .format import format_info


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _stale_days(entry) -> Optional[int]:
    value = entry.last_verified_at or entry.verified_at
    if not value:
        return None
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None
    return max(0, (_today() - parsed).days)


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


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFC", str(value or "")).casefold()


def _matched_by(entry, needle: str) -> str:
    if not needle:
        return "none"
    q = _normalize(needle)
    if q in _normalize(entry.id):
        return "id"
    if q in _normalize(entry.label):
        return "label"
    for alias in entry.aliases:
        if q in _normalize(alias):
            return "alias"
    return "none"


def _item(entry, needle: str) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "label": entry.label,
        "kind": entry.kind,
        "group": entry.group,
        "source_type": entry.source_type,
        "verification_status": entry.verification_status,
        "evidence_level": entry.evidence_level,
        "verified_at": entry.verified_at,
        "last_verified_at": entry.last_verified_at,
        "stale_days": _stale_days(entry),
        "aliases": list(entry.aliases),
        "batch": entry.batch,
        "origin": entry.origin,
        "source": entry.source,
        "limits": _limits(entry),
        "legacy_limits_present": entry.legacy_limits is not None,
        "is_selectable": True,
        "requires_confirm": entry.verification_status == "unknown",
        "stale": entry.verification_status == "verified" and (_stale_days(entry) or 0) >= 90,
        "strong_stale": entry.verification_status == "verified" and (_stale_days(entry) or 0) >= 180,
        "matched_by": _matched_by(entry, needle),
        "notes": entry.notes,
        "unknown_fields": list(entry.unknown_fields),
        "format": format_info(entry),
    }


def _filter_entries(entries: List[Any], params: Dict[str, Any]) -> List[Any]:
    result = []
    for entry in entries:
        if params.get("kind") and entry.kind != params["kind"]:
            continue
        if params.get("group") and entry.group != params["group"]:
            continue
        if params.get("verified") is True and entry.verification_status != "verified":
            continue
        if params.get("verified") is False and entry.verification_status != "unknown":
            continue
        if params.get("evidence") and entry.evidence_level != params["evidence"]:
            continue
        if params.get("q") and _matched_by(entry, params["q"]) == "none":
            continue
        result.append(entry)
    return result


def _sort(entries: List[Any], sort_key: str) -> List[Any]:
    if sort_key == "group":
        return sorted(entries, key=lambda item: (item.group, item.id))
    if sort_key == "label":
        return sorted(entries, key=lambda item: (item.label.casefold(), item.id))
    return sorted(entries, key=lambda item: (0 if item.verification_status == "verified" else 1, item.id))


def _counts(registry) -> Dict[str, Any]:
    counts = registry.counts().as_dict()
    evidence = registry.evidence()
    if evidence:
        evidence_counts = registry.evidence_counts()
        counts.update(
            {
                "evidence_total": evidence_counts.evidence_total,
                "evidence_skill": evidence_counts.evidence_skill,
                "evidence_rules": evidence_counts.evidence_rules,
                "evidence_discovery": evidence_counts.evidence_discovery,
            }
        )
    else:
        counts.update(
            {"evidence_total": None, "evidence_skill": None, "evidence_rules": None, "evidence_discovery": None}
        )
    return counts


def query_platforms(registry, params: Dict[str, Any]) -> Dict[str, Any]:
    entries = registry.entries()
    filtered = _filter_entries(entries, params)
    filtered = _sort(filtered, params.get("sort", "status"))
    total = len(filtered)
    limit = int(params.get("limit", 0) or 0)
    offset = int(params.get("offset", 0) or 0)
    page_items = filtered[offset:] if limit == 0 else filtered[offset:offset + limit]
    items = [_item(entry, params.get("q", "")) for entry in page_items]
    evidence = registry.evidence()
    counts = _counts(registry)
    sources = {
        "discovery_round": evidence.get("round") if evidence else None,
        "generated_at": evidence.get("generated_at") if evidence else None,
        "record_path": evidence.get("record_path") if evidence else None,
    }
    return {
        "items": items,
        "page": {"limit": limit, "offset": offset, "total": total},
        "total": counts["total"],
        "counts": counts,
        "evidence": (
            {
                "probed": evidence.get("probed"),
                "ok": evidence.get("ok"),
                "failed": evidence.get("failed"),
                "no_evidence": evidence.get("no_evidence"),
                "by_level": evidence.get("by_level"),
            }
            if evidence
            else None
        ),
        "diagnostics": registry.diagnostics(),
        "sources": sources,
    }