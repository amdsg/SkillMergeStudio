from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ....util.errors import DomainError

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_DATE_FORMAT = "%Y-%m-%d"


def _issue(code: str, field: str, message: str, fix: str) -> Dict[str, str]:
    return {"code": code, "field": field, "message": message, "fix": fix}


def load_schema(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise DomainError("PLATFORM_SCHEMA_MISSING", "缺少 platforms/schema.json", "恢复 v2 schema 后重启", 500)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            schema = json.load(handle)
    except (OSError, ValueError) as exc:
        raise DomainError("PLATFORM_SCHEMA_INVALID", f"schema.json 读取失败：{exc}", "修复 JSON 后重启", 500)
    if not isinstance(schema, dict) or int(schema.get("schema_version", 0)) != 2:
        raise DomainError("PLATFORM_SCHEMA_INVALID", "schema_version 必须为 2", "使用 v2 schema", 500)
    for key in ("required", "enums", "rule_body_fields", "rule_body_required", "baseline_ids"):
        if key not in schema:
            raise DomainError("PLATFORM_SCHEMA_INVALID", f"schema 缺少 {key}", "补齐 schema 后重启", 500)
    return schema


def is_valid_date(value: Any) -> bool:
    if value is None:
        return True
    try:
        parsed = datetime.strptime(str(value), _DATE_FORMAT).date()
    except ValueError:
        return False
    today = datetime.now(timezone.utc).date()
    return date(2000, 1, 1) <= parsed <= today + timedelta(days=1)


def _body_issues(entry: Dict[str, Any], schema: Dict[str, Any]) -> List[Dict[str, str]]:
    issues = []
    for field in schema["rule_body_fields"]:
        value = entry.get(field)
        if not isinstance(value, dict):
            issues.append(_issue("C-13", field, f"规则体 {field} 不是对象", "verified 条目必须提供完整规则体"))
            continue
        for child in schema["rule_body_required"].get(field, []):
            if child not in value:
                issues.append(_issue("C-13", f"{field}.{child}", f"{field} 缺少 {child}", "补齐规则体字段"))
    return issues


def validate_entry(entry: Dict[str, Any], schema: Dict[str, Any], filename: str) -> List[Dict[str, str]]:
    issues = []
    missing = [key for key in schema["required"] if key not in entry]
    if missing:
        issues.append(_issue("C-02", "required", f"缺少治理字段：{', '.join(missing)}", "补齐 16 个治理字段"))
        return issues
    entry_id = str(entry.get("id", ""))
    if not ID_PATTERN.fullmatch(entry_id):
        issues.append(_issue("C-03", "id", f"id 不符合规则：{entry_id}", "使用小写字母、数字与连字符，2–64 字符"))
    stem = os.path.splitext(os.path.basename(filename))[0]
    if stem != entry_id:
        issues.append(_issue("C-04", "id", f"文件名 {stem} 与 id {entry_id} 不一致", "将文件命名为 <id>.json"))
    label = str(entry.get("label", "")).strip()
    if not label or len(label) > 80:
        issues.append(_issue("C-05", "label", "label 必须为 1–80 字符", "填写展示名"))
    for field in ("kind", "group", "source_type", "verification_status", "evidence_level", "origin"):
        allowed = schema["enums"].get(field, [])
        if entry.get(field) not in allowed:
            issues.append(_issue("C-06", field, f"{field} 不在允许枚举内", f"使用：{allowed}"))
    if entry.get("source_type") == "local_contract":
        source = entry.get("source")
        if not isinstance(source, str) or not source.startswith(schema.get("source_type_local_prefix", "local://")):
            issues.append(_issue("C-08", "source", "local_contract 必须使用 local://", "修正 source 或 source_type"))
    if entry.get("origin") == "baseline" and entry_id not in schema["baseline_ids"]:
        issues.append(_issue("C-15", "origin", f"{entry_id} 不在基线集合", "新增条目使用 origin=new"))
    if point_in_evidence_forbidden(entry, schema):
        issues.append(_issue("C-18", "evidence_level", "条目不得使用发现/失败/无证据级别", "改为 candidate_skill/candidate_rules"))
    if not is_valid_date(entry.get("verified_at")) or not is_valid_date(entry.get("last_verified_at")):
        issues.append(_issue("C-17", "verified_at", "日期必须为 YYYY-MM-DD 或 null", "修正日期"))
    if entry.get("verification_status") == "verified":
        if not entry.get("source"):
            issues.append(_issue("C-11", "source", "verified 条目必须有 source", "填写官方 URL 或 local://"))
        if not entry.get("verified_at"):
            issues.append(_issue("C-11", "verified_at", "verified 条目必须有 verified_at", "填写核验日期"))
        if entry.get("evidence_level") != "verified":
            issues.append(_issue("C-10", "evidence_level", "verified 条目 evidence_level 必须为 verified", "修正 evidence_level"))
        if entry.get("unknown_fields"):
            issues.append(_issue("C-11", "unknown_fields", "verified 条目 unknown_fields 必须为空", "清空 unknown_fields"))
        issues.extend(_body_issues(entry, schema))
    elif entry.get("verification_status") == "unknown":
        if entry.get("source") is not None:
            issues.append(_issue("C-12", "source", "unknown 条目 source 必须为 null", "不要填写未核验来源"))
        if entry.get("verified_at") is not None:
            issues.append(_issue("C-12", "verified_at", "unknown 条目 verified_at 必须为 null", "不要填写未核验日期"))
        if entry.get("evidence_level") not in ("candidate_skill", "candidate_rules"):
            issues.append(_issue("C-12", "evidence_level", "unknown 条目证据级别必须为 candidate_skill/candidate_rules", "修正证据级别"))
        fields = entry.get("unknown_fields")
        if not isinstance(fields, list) or not fields:
            issues.append(_issue("C-12", "unknown_fields", "unknown 条目 unknown_fields 不能为空", "列出未核验字段"))
        if not str(entry.get("notes", "")).strip():
            issues.append(_issue("C-16", "notes", "unknown 条目 notes 不能为空", "填写未核验原因与最近尝试日期"))
        for field in schema["rule_body_fields"]:
            if entry.get(field) is not None:
                issues.append(_issue("C-13", field, "unknown 条目的规则体必须为 null", "将原值移入 legacy_limits"))
        if entry.get("legacy_limits") is not None and entry.get("origin") != "baseline":
            issues.append(_issue("C-20", "legacy_limits", "legacy_limits 只允许基线迁移条目", "删除 legacy_limits"))
    aliases = entry.get("aliases")
    if not isinstance(aliases, list) or any(not str(item).strip() for item in aliases):
        issues.append(_issue("C-14", "aliases", "aliases 必须为非空字符串数组", "修正 aliases"))
    return issues


def point_in_evidence_forbidden(entry: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    return entry.get("evidence_level") in schema.get("forbid_in_registry", [])


def validate_aliases(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    ids = {str(entry["id"]) for entry in entries}
    owner: Dict[str, str] = {}
    issues = []
    for entry in entries:
        for alias in entry.get("aliases") or []:
            alias = str(alias).strip()
            if not alias:
                continue
            if alias in ids:
                issues.append(_issue("C-14", "aliases", f"别名 {alias} 与平台 id 冲突", "改用非 id 的别名"))
            if alias == str(entry["id"]):
                issues.append(_issue("C-14", "aliases", "别名不能等于自身 id", "删除该别名"))
            if alias in owner and owner[alias] != str(entry["id"]):
                issues.append(_issue("C-14", "aliases", f"别名 {alias} 被多个条目使用", "保证别名全局唯一"))
            owner[alias] = str(entry["id"])
    return issues


def validate_baseline(entries: Iterable[Dict[str, Any]], schema: Dict[str, Any]) -> List[Dict[str, str]]:
    ids = {str(entry["id"]) for entry in entries}
    missing = [item for item in schema["baseline_ids"] if item not in ids]
    if not missing:
        return []
    return [_issue("C-19", "baseline_ids", f"基线条目缺失：{', '.join(missing)}", "恢复基线文件，不得用新 id 替代")]


def raise_issues(issues: List[Dict[str, str]], source: str) -> None:
    if not issues:
        return
    first = issues[0]
    raise DomainError(
        "PLATFORM_RULE_INVALID",
        f"{source} 校验失败：{first['message']}",
        first["fix"],
        500,
        {"file": source, "issues": issues[:20], "total": len(issues)},
    )