from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ....util.errors import DomainError
from . import diagnostics as diagnostics_module
from .counts import EvidenceCounts, RegistryCounts, build_evidence_counts, build_registry_counts
from .discovery_reader import load_latest
from .migrate_v1 import normalize_v1, normalize_v2
from .schema_rules import load_schema, raise_issues, validate_aliases, validate_baseline, validate_entry


@dataclass(frozen=True)
class PlatformEntry:
    id: str
    label: str
    kind: str
    group: str
    origin: str
    batch: str
    source: Optional[str]
    source_type: str
    verification_status: str
    evidence_level: str
    verified_at: Optional[str]
    last_verified_at: Optional[str]
    unknown_fields: Tuple[str, ...]
    notes: str
    aliases: Tuple[str, ...]
    legacy_limits: Optional[Dict[str, Any]]
    rule_body: Optional[Dict[str, Any]]

    def as_rule(self) -> Dict[str, Any]:
        base = dict(self.rule_body or self.legacy_limits or {})
        base.update(
            {
                "rule_schema_version": 2,
                "id": self.id,
                "label": self.label,
                "kind": self.kind,
                "group": self.group,
                "origin": self.origin,
                "batch": self.batch,
                "source": self.source if self.source is not None else "unknown",
                "source_type": self.source_type,
                "verification_status": self.verification_status,
                "evidence_level": self.evidence_level,
                "verified_at": self.verified_at if self.verified_at is not None else "unknown",
                "last_verified_at": self.last_verified_at,
                "unknown_fields": list(self.unknown_fields),
                "notes": self.notes,
                "aliases": list(self.aliases),
                "legacy_limits": self.legacy_limits,
            }
        )
        return base

    def as_public(self) -> Dict[str, Any]:
        rule = self.as_rule()
        body = self.rule_body or self.legacy_limits
        limits = None
        limits_source = "none"
        if body:
            limits = {
                "name_max_length": body["name"]["max_length"],
                "description_max_chars": body["description"]["max_chars"],
                "bundle_max_mb": body["bundle"]["max_mb"],
                "bundle_max_files": body["bundle"]["max_files"],
                "package_type": body["package"]["type"],
            }
            limits_source = "verified" if self.rule_body else "legacy_limits"
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "group": self.group,
            "verification_status": self.verification_status,
            "evidence_level": self.evidence_level,
            "verified_at": self.verified_at or "unknown",
            "last_verified_at": self.last_verified_at,
            "source": self.source or "unknown",
            "source_type": self.source_type,
            "unknown": self.verification_status == "unknown",
            "stale": self.verification_status == "verified"
            and _age_days(self.verified_at) >= 90,
            "strong_stale": self.verification_status == "verified"
            and _age_days(self.verified_at) >= 180,
            "notes": self.notes,
            "aliases": list(self.aliases),
            "unknown_fields": list(self.unknown_fields),
            "legacy_limits_present": self.legacy_limits is not None,
            "limits": limits,
            "limits_source": limits_source,
            "rule": rule,
        }


@dataclass
class PlatformLoadResult:
    entries: List[PlatformEntry]
    counts: RegistryCounts
    evidence: Optional[Dict[str, Any]]
    diagnostics: List[Dict[str, Any]]
    schema: Dict[str, Any]
    normalized: List[str]
    records: List[Dict[str, Any]] = field(default_factory=list)

    def entry(self, platform_id: str) -> Optional[PlatformEntry]:
        for item in self.entries:
            if item.id == str(platform_id):
                return item
        return None


def _age_days(value: Optional[str]) -> int:
    from datetime import datetime, timezone

    if not value:
        return 9999
    try:
        parsed = datetime.strptime(str(value), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return 9999
    return (datetime.now(timezone.utc) - parsed).days


def _read(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError) as exc:
        raise DomainError("PLATFORM_RULE_INVALID", f"{os.path.basename(path)} 读取失败：{exc}", "修复 JSON 后重启", 500)
    if not isinstance(raw, dict):
        raise DomainError("PLATFORM_RULE_INVALID", f"{os.path.basename(path)} 顶层不是对象", "使用 JSON object", 500)
    return raw


def _normalize(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    version = raw.get("rule_schema_version", 1)
    try:
        version = int(version)
    except (TypeError, ValueError):
        raise DomainError("PLATFORM_RULE_INVALID", "rule_schema_version 非法", "使用 1 或 2", 500)
    if version == 1:
        return normalize_v1(raw), True
    if version == 2:
        return normalize_v2(raw), False
    raise DomainError("PLATFORM_RULE_INVALID", f"rule_schema_version={version} 不受支持", "使用 1 或 2", 500)


def _build_entry(normalized: Dict[str, Any]) -> PlatformEntry:
    body = {key: normalized.get(key) for key in ("name", "description", "skill_md", "bundle", "package", "frontmatter", "install")}
    body = {key: value for key, value in body.items() if value is not None} if normalized["verification_status"] == "verified" else None
    return PlatformEntry(
        id=str(normalized["id"]),
        label=str(normalized["label"]),
        kind=str(normalized["kind"]),
        group=str(normalized["group"]),
        origin=str(normalized["origin"]),
        batch=str(normalized["batch"]),
        source=normalized.get("source"),
        source_type=str(normalized["source_type"]),
        verification_status=str(normalized["verification_status"]),
        evidence_level=str(normalized["evidence_level"]),
        verified_at=normalized.get("verified_at"),
        last_verified_at=normalized.get("last_verified_at"),
        unknown_fields=tuple(normalized.get("unknown_fields") or ()),
        notes=str(normalized.get("notes") or ""),
        aliases=tuple(normalized.get("aliases") or ()),
        legacy_limits=normalized.get("legacy_limits"),
        rule_body=body,
    )


def _load_entries(directory: str, schema: Dict[str, Any]):
    entries: List[PlatformEntry] = []
    normalized_names: List[str] = []
    issues = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json") or name in ("schema.json", "leads.json"):
            continue
        if name.startswith("summary-") or name.endswith(".meta.json"):
            continue
        path = os.path.join(directory, name)
        if not os.path.isfile(path):
            continue
        raw = _read(path)
        normalized, was_v1 = _normalize(raw)
        entry_issues = validate_entry(normalized, schema, name)
        if entry_issues:
            issues.extend(entry_issues)
            continue
        entries.append(_build_entry(normalized))
        if was_v1:
            normalized_names.append(name)
    if issues:
        raise_issues(issues, "platforms")
    return entries, normalized_names


def load_registry(directory: str, discovery_directory: Optional[str] = None) -> PlatformLoadResult:
    if not os.path.isdir(directory):
        raise DomainError("PLATFORM_RULES_MISSING", "平台规则目录不存在", "恢复 platforms/ 目录后重启", 500)
    schema = load_schema(os.path.join(directory, "schema.json"))
    entries, normalized_names = _load_entries(directory, schema)
    ids = [entry.id for entry in entries]
    if len(set(ids)) != len(ids):
        raise DomainError("PLATFORM_RULE_INVALID", "平台 id 重复", "保证 id 唯一", 500)
    raw_entries = [entry.as_rule() for entry in entries]
    alias_issues = validate_aliases(raw_entries)
    baseline_issues = validate_baseline(raw_entries, schema)
    if alias_issues or baseline_issues:
        raise_issues(alias_issues + baseline_issues, "platforms")
    entries.sort(key=lambda item: item.id)
    counts = build_registry_counts(entries)
    discovery = load_latest(discovery_directory or os.path.join(directory, "discovery"))
    evidence = discovery.summary if discovery is not None else None
    evidence_counts = build_evidence_counts(evidence) if evidence else None
    diagnostics = diagnostics_module.diagnose(counts, entries, evidence_counts)
    if discovery is not None:
        diagnostics.extend(discovery.issues)
    else:
        diagnostics.append(
            {
                "code": "DISCOVERY_MISSING",
                "severity": "warn",
                "message": "本轮无探测记录",
                "files": [],
                "fix": "运行 tools/validate_discovery.py 或保留空态",
                "items": [],
            }
        )
    return PlatformLoadResult(
        entries=entries,
        counts=counts,
        evidence=evidence,
        diagnostics=diagnostics,
        schema=schema,
        normalized=normalized_names,
        records=discovery.records if discovery else [],
    )