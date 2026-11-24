"""Registry loader and structural validation shared by the agent API."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ROOT / "agent" / "adapters"
EVIDENCE = ROOT / "agent" / "evidence" / "targets"

ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
ADAPTER_RE = re.compile(r"^(builtin:[a-z0-9_]+@\d+|engine:[a-z0-9_/-]+)$")
KINDS = {"skill", "prompt", "generic"}
LEVELS = {"verified", "candidate", "unknown"}
SUBTYPES = {"official", "local_contract"}
SOURCE_TYPES = {"official_docs", "local_contract", "none"}
FAMILIES = {"skill_md", "prompt_text", "rules_md", "config_json", "bundle_zip", "generic_text", "unknown"}
GENERIC_PLATFORMS = {"generic", "agent-skills", "prompt-only"}


def _load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def validate(items: list[dict], group_ids: set[str], tool_ids: set[str]) -> list[dict]:
    errors = []
    seen = set()
    aliases = {}
    for item in items:
        target_id = str(item.get("id", ""))
        if not ID_RE.match(target_id):
            errors.append(_error("id", "invalid_id", target_id))
        if target_id in seen:
            errors.append(_error("id", "duplicate_id", target_id))
        seen.add(target_id)
        if item.get("kind") not in KINDS:
            errors.append(_error("kind", "invalid_enum", target_id))
        level = str(item.get("evidence_level", ""))
        if level not in LEVELS:
            errors.append(_error("evidence_level", "invalid_enum", target_id))
        source = str(item.get("source", "") or "")
        subtype = item.get("evidence_subtype")
        if level == "verified" and (subtype not in SUBTYPES or not source or not item.get("verified_at")):
            errors.append(_error("evidence_subtype", "missing_verified_fields", target_id))
        if subtype == "official" and item.get("source_type") != "official_docs":
            errors.append(_error("source_type", "official_mismatch", target_id))
        if subtype == "local_contract" and item.get("source_type") != "local_contract":
            errors.append(_error("source_type", "local_contract_mismatch", target_id))
        if level == "unknown" and (source or item.get("source_type") != "none" or not item.get("unknown_fields")):
            errors.append(_error("unknown_fields", "unknown_with_source", target_id))
        if level == "candidate" and (item.get("format_profile") != "unknown" or not item.get("unknown_fields")):
            errors.append(_error("format_profile", "candidate_preset_format", target_id))
        if item.get("format_family") not in FAMILIES:
            errors.append(_error("format_family", "invalid_enum", target_id))
        if level != "verified" and item.get("format_family") not in {"unknown", "generic_text"}:
            errors.append(_error("format_family", "unverified_family", target_id))
        if str(item.get("group", "")) not in group_ids:
            errors.append(_error("group", "unknown_group", target_id))
        if len(str(item.get("notes", ""))) < 8:
            errors.append(_error("notes", "notes_too_short", target_id))
        provenance = item.get("provenance") or {}
        for field in ("added_by", "added_at", "rationale", "upstream_ref"):
            if not str(provenance.get(field, "")):
                errors.append(_error(f"provenance.{field}", "missing_field", target_id))
        adapter = item.get("adapter") or {}
        for field in ("detector", "converter"):
            if not ADAPTER_RE.match(str(adapter.get(field, ""))):
                errors.append(_error(f"adapter.{field}", "invalid_adapter", target_id))
        for hint in item.get("tool_hints") or []:
            if hint not in tool_ids:
                errors.append(_error("tool_hints", "unknown_tool", target_id))
        if item.get("kind") == "generic":
            platform = str((item.get("mapped_engine") or {}).get("platform", ""))
            if platform and platform not in GENERIC_PLATFORMS:
                errors.append(_error("mapped_engine", "generic_mapped_to_platform", target_id))
        evidence_path = EVIDENCE / f"{target_id}.json"
        if not evidence_path.is_file():
            errors.append(_error("entry_version", "missing_evidence_history", target_id))
        for alias in item.get("aliases") or []:
            if alias in aliases:
                errors.append(_error("aliases", "duplicate_alias", target_id))
            aliases[alias] = target_id
    enabled = [item for item in items if item.get("enabled", True)]
    counts = {"total": len(enabled), "verified": 0, "candidate": 0, "unknown": 0, "disabled": len(items) - len(enabled)}
    subtype_counts = {"official": 0, "local_contract": 0}
    for item in enabled:
        level = str(item.get("evidence_level"))
        if level in counts:
            counts[level] += 1
        if level == "verified":
            subtype_counts[str(item.get("evidence_subtype"))] = subtype_counts.get(str(item.get("evidence_subtype")), 0) + 1
    if counts["total"] != counts["verified"] + counts["candidate"] + counts["unknown"]:
        errors.append({"file": "targets.json", "field": "counts", "code": "count_identity", "target": ""})
    if counts["verified"] != subtype_counts["official"] + subtype_counts["local_contract"]:
        errors.append({"file": "targets.json", "field": "counts", "code": "subtype_identity", "target": ""})
    return errors


def _error(field: str, code: str, target: str) -> dict:
    return {"file": "targets.json", "field": field, "code": code, "target": target}


class TargetRegistry:
    def __init__(self) -> None:
        self.items: list[dict] = []
        self.groups: list[dict] = []
        self.counts: dict = {}
        self.errors: list[dict] = []
        self.tool_hints: list[dict] = []
        self.mapping: dict = {}
        self.reload()

    def reload(self) -> None:
        items = _load(ADAPTERS / "targets.json", [])
        groups = _load(ADAPTERS / "target_groups.json", [])
        tool_hints = _load(ADAPTERS / "tool_hints.json", [])
        mapping = _load(ADAPTERS / "mapping.json", {})
        tool_ids = {
            str(_load(path, {}).get("tool_id"))
            for path in (ROOT / "agent" / "evidence" / "tools").glob("*.json")
        }
        group_ids = {str(group.get("group_id")) for group in groups if isinstance(groups, dict) or isinstance(group, dict)}
        self.errors = validate(items if isinstance(items, list) else [], group_ids, tool_ids)
        self.items = [item for item in items if item.get("enabled", True)] if isinstance(items, list) else []
        self.groups = groups if isinstance(groups, list) else []
        self.tool_hints = tool_hints if isinstance(tool_hints, list) else []
        self.mapping = mapping if isinstance(mapping, dict) else {}
        enabled = self.items
        counts = {"total": len(enabled), "verified": 0, "verified_official": 0, "verified_local_contract": 0, "candidate": 0, "unknown": 0, "disabled": len(items) - len(enabled) if isinstance(items, list) else 0}
        by_family: dict[str, int] = {}
        by_group: dict[str, int] = {}
        for item in enabled:
            level = str(item.get("evidence_level"))
            counts[level] = counts.get(level, 0) + 1
            if level == "verified":
                subtype = str(item.get("evidence_subtype"))
                key = f"verified_{subtype}"
                counts[key] = counts.get(key, 0) + 1
            family = str(item.get("format_family", "unknown"))
            by_family[family] = by_family.get(family, 0) + 1
            group = str(item.get("group", "unknown"))
            by_group[group] = by_group.get(group, 0) + 1
        counts["by_family"] = dict(sorted(by_family.items()))
        counts["by_group"] = dict(sorted(by_group.items()))
        self.counts = counts

    def get(self, target_id: str) -> dict | None:
        return next((item for item in self.items if item.get("id") == target_id), None)

    def sample_ids(self) -> list[str]:
        samples = [str(item.get("id")) for item in self.items if item.get("evidence_level") == "verified"][:5]
        return samples

    def diagnostics(self) -> list[dict]:
        return self.errors


registry = TargetRegistry()