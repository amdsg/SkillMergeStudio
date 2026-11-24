#!/usr/bin/env python3
"""Target adapter registry gate (C-WB-01~23, dynamic matrix, count identities)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADAPTERS = ROOT / "agent" / "adapters"
TARGETS = ADAPTERS / "targets.json"
GROUPS = ADAPTERS / "target_groups.json"
TOOL_HINTS = ADAPTERS / "tool_hints.json"
MAPPING = ADAPTERS / "mapping.json"
REMOVED = ADAPTERS / "removed.json"
EVIDENCE = ROOT / "agent" / "evidence" / "targets"
TOOLS = ROOT / "agent" / "evidence" / "tools"

KINDS = {"skill", "prompt", "generic"}
LEVELS = {"verified", "candidate", "unknown"}
SUBTYPES = {"official", "local_contract"}
SOURCE_TYPES = {"official_docs", "local_contract", "none"}
FAMILIES = {"skill_md", "prompt_text", "rules_md", "config_json", "bundle_zip", "generic_text", "unknown"}
GENERIC_PLATFORMS = {"generic", "agent-skills", "prompt-only"}
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
REF_RE = re.compile(r"^ref:[a-z0-9_]+:[a-z0-9_]+@[a-z0-9_.]+$")
ADAPTER_RE = re.compile(r"^(builtin:[a-z0-9_]+@\d+|engine:[a-z0-9_/-]+)$")
FORBIDDEN_NUMERIC = {"max_chars", "max_bytes", "max_files", "max_mb", "forbidden_parts", "install", "package"}


def load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def validate(items, groups, tool_ids):
    errors: list[str] = []
    ids: dict[str, int] = {}
    aliases: dict[str, str] = {}
    group_ids = {str(group.get("group_id")) for group in groups}
    for item in items:
        target_id = str(item.get("id", ""))
        prefix = f"C-WB"
        if not ID_RE.match(target_id):
            errors.append(f"{prefix}-01 {target_id or '<empty>'}: invalid id")
        ids[target_id] = ids.get(target_id, 0) + 1
        kind = str(item.get("kind", ""))
        if kind not in KINDS:
            errors.append(f"{prefix}-02 {target_id}: kind={kind}")
        level = str(item.get("evidence_level", ""))
        if level not in LEVELS:
            errors.append(f"{prefix}-03 {target_id}: evidence_level={level}")
        subtype = item.get("evidence_subtype")
        source = str(item.get("source", "") or "")
        source_type = str(item.get("source_type", ""))
        verified_at = item.get("verified_at")
        unknown_fields = item.get("unknown_fields") or []
        if level == "verified":
            if subtype not in SUBTYPES:
                errors.append(f"{prefix}-04 {target_id}: missing subtype")
            if not source:
                errors.append(f"{prefix}-04 {target_id}: missing source")
            if not verified_at:
                errors.append(f"{prefix}-04 {target_id}: missing verified_at")
        if subtype == "official":
            if source_type != "official_docs" or not source.startswith(("http://", "https://")):
                errors.append(f"{prefix}-05 {target_id}: official source mismatch")
        if subtype == "local_contract" and source_type != "local_contract":
            errors.append(f"{prefix}-06 {target_id}: local_contract source mismatch")
        if level == "unknown":
            if source or source_type != "none" or not unknown_fields:
                errors.append(f"{prefix}-07 {target_id}: unknown must have no source and non-empty unknown_fields")
        if level == "candidate":
            if item.get("format_profile") != "unknown" or not unknown_fields:
                errors.append(f"{prefix}-08 {target_id}: candidate must not preset format")
        profile = str(item.get("format_profile", ""))
        if profile.startswith("ref:"):
            if not REF_RE.match(profile) or item.get("mapped_engine") is None:
                errors.append(f"{prefix}-09 {target_id}: unresolved ref {profile}")
        if len(str(item.get("notes", ""))) < 8:
            errors.append(f"{prefix}-10 {target_id}: notes too short")
        if level != "verified" and FORBIDDEN_NUMERIC.intersection(item):
            errors.append(f"{prefix}-13 {target_id}: numeric fields on unverified target")
        mapped = item.get("mapped_engine") or {}
        if kind == "generic":
            platform = str(mapped.get("platform", ""))
            if platform and platform not in GENERIC_PLATFORMS:
                errors.append(f"{prefix}-14 {target_id}: generic mapped to platform {platform}")
        evidence_path = EVIDENCE / f"{target_id}.json"
        evidence = load(evidence_path, None)
        if not isinstance(evidence, dict):
            errors.append(f"{prefix}-15 {target_id}: missing evidence history")
        elif int(evidence.get("entry_version", 0)) != int(item.get("entry_version", 0)):
            errors.append(f"{prefix}-15 {target_id}: entry_version mismatch")
        if str(item.get("group", "")) not in group_ids:
            errors.append(f"{prefix}-17 {target_id}: unknown group {item.get('group')}")
        family = str(item.get("format_family", ""))
        if family not in FAMILIES:
            errors.append(f"{prefix}-19 {target_id}: format_family={family}")
        if level != "verified" and family not in {"unknown", "generic_text"}:
            errors.append(f"{prefix}-19 {target_id}: unverified family={family}")
        provenance = item.get("provenance") or {}
        for field in ("added_by", "added_at", "rationale", "upstream_ref"):
            if not str(provenance.get(field, "")):
                errors.append(f"{prefix}-20 {target_id}: provenance missing {field}")
        adapter = item.get("adapter") or {}
        for field in ("detector", "converter"):
            if not ADAPTER_RE.match(str(adapter.get(field, ""))):
                errors.append(f"{prefix}-21 {target_id}: adapter {field} invalid")
        for hint in item.get("tool_hints") or []:
            if hint not in tool_ids:
                errors.append(f"{prefix}-22 {target_id}: unknown tool {hint}")
        if not isinstance(item.get("enabled"), bool):
            errors.append(f"{prefix}-23 {target_id}: enabled must be boolean")
        for alias in item.get("aliases") or []:
            if alias in aliases:
                errors.append(f"C-WB-18 {target_id}: duplicate alias {alias}")
            aliases[alias] = target_id
    for target_id, count in ids.items():
        if count > 1:
            errors.append(f"C-WB-01 {target_id}: duplicate id")
    for alias, owner in aliases.items():
        if alias in ids or any(alias == str(item.get("label")) for item in items):
            errors.append(f"C-WB-18 {owner}: alias equals id/label {alias}")
    enabled = [item for item in items if item.get("enabled", True)]
    disabled = [item for item in items if not item.get("enabled", True)]
    counts = {"total": len(enabled), "verified": 0, "candidate": 0, "unknown": 0, "disabled": len(disabled)}
    subtypes = {"official": 0, "local_contract": 0}
    for item in enabled:
        level = str(item.get("evidence_level"))
        if level in counts:
            counts[level] += 1
        if level == "verified":
            subtypes[str(item.get("evidence_subtype"))] = subtypes.get(str(item.get("evidence_subtype")), 0) + 1
    if counts["total"] != counts["verified"] + counts["candidate"] + counts["unknown"]:
        errors.append(f"C-WB-11 total mismatch {counts}")
    if counts["verified"] != subtypes["official"] + subtypes["local_contract"]:
        errors.append(f"C-WB-12 verified subtype mismatch {subtypes}")
    for removed in (load(REMOVED, {}).get("removed") or []):
        if removed.get("id") in ids:
            errors.append(f"C-WB-15 {removed.get('id')}: removed target still listed")
    return errors, counts


def build_matrix(items):
    cases = []
    for item in [entry for entry in items if entry.get("enabled", True)]:
        cases.append({"target_id": item["id"], "case": "conform", "checks": ["C-WB-01", "C-WB-10"]})
        cases.append({"target_id": item["id"], "case": "violation", "checks": ["C-WB-01 duplicate id", "C-WB-07 unknown with source"]})
    return cases


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="adapter registry gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--assert-counts", action="store_true")
    parser.add_argument("--assert-groups", action="store_true")
    parser.add_argument("--assert-evidence", action="store_true")
    parser.add_argument("--assert-wording", action="store_true")
    parser.add_argument("--matrix-out", default="")
    args = parser.parse_args(argv)
    if not TARGETS.is_file():
        print("WB-REGISTRY: targets.json missing", file=sys.stderr)
        return 2
    items = load(TARGETS, [])
    if not isinstance(items, list) or not items:
        print("WB-REGISTRY: targets.json must be a non-empty array", file=sys.stderr)
        return 2
    groups = load(GROUPS, [])
    tool_ids = {str(load(path, {}).get("tool_id")) for path in TOOLS.glob("*.json")} if TOOLS.is_dir() else set()
    errors, counts = validate(items, groups if isinstance(groups, list) else [], tool_ids)
    if args.assert_groups:
        group_ids = [str(group.get("group_id")) for group in groups if isinstance(groups, list)]
        if len(set(group_ids)) != len(group_ids):
            errors.append("C-WB-17 duplicate group_id")
    if args.assert_evidence:
        for item in items:
            if not (EVIDENCE / f"{item.get('id')}.json").is_file():
                errors.append(f"C-WB-15 {item.get('id')}: evidence missing")
    if args.assert_counts:
        print(f"WB-COUNTS: total={counts['total']} verified={counts['verified']} candidate={counts['candidate']} unknown={counts['unknown']} disabled={counts['disabled']}")
    if args.matrix_out:
        matrix = build_matrix(items)
        out = Path(args.matrix_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"cases": matrix, "case_count": len(matrix)}, ensure_ascii=False, indent=1), encoding="utf-8")
        expected = len([entry for entry in items if entry.get("enabled", True)]) * 2
        if len(matrix) != expected:
            errors.append(f"MATRIX-COUNT: expected {expected} actual {len(matrix)}")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-REGISTRY: errors={len(errors)} targets={len(items)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())