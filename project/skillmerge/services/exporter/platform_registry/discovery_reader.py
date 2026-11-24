from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

ALLOWED_FIELDS = {
    "key",
    "label",
    "url",
    "final_url",
    "status",
    "error",
    "title",
    "bytes_read",
    "markers",
}
DISCOVERY_LEVELS = ("candidate_skill", "candidate_rules", "discovery_source", "no_evidence", "failed_unreachable")


@dataclass
class DiscoveryResult:
    summary: Optional[Dict[str, Any]]
    records: List[Dict[str, Any]]
    issues: List[Dict[str, Any]]
    round_name: str = ""


def _issue(code: str, message: str, fix: str, key: str = "", severity: str = "warn") -> Dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "files": [key] if key else [],
        "fix": fix,
        "items": [],
    }


def grade(record: Dict[str, Any], discovery_keys: Tuple[str, ...]) -> str:
    key = str(record.get("key", ""))
    if key in discovery_keys:
        return "discovery_source"
    status = record.get("status")
    if status is None or int(status) >= 400:
        return "failed_unreachable"
    if int(status) == 200:
        markers = record.get("markers") or {}
        if markers.get("skill_md"):
            return "candidate_skill"
        if markers.get("rules_word") or markers.get("agents_md") or markers.get("agent_skills"):
            return "candidate_rules"
        return "no_evidence"
    return "failed_unreachable"


def _meta_for(path: str) -> Tuple[List[str], bool]:
    meta_path = os.path.splitext(path)[0] + ".meta.json"
    if not os.path.isfile(meta_path):
        return [], False
    try:
        with open(meta_path, "r", encoding="utf-8") as handle:
            meta = json.load(handle)
    except (OSError, ValueError):
        return [], False
    keys = meta.get("discovery_keys") or []
    return [str(item) for item in keys], True


def _validate_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    issues = []
    seen_urls = set()
    for record in records:
        key = str(record.get("key", ""))
        extra = set(record.keys()) - ALLOWED_FIELDS
        if extra:
            issues.append(_issue("DISCOVERY_FIELD_INVALID", f"{key} 含越界字段：{sorted(extra)}", "删除规则字段"))
        if any(field in record for field in ("limits", "source", "verified_at")):
            issues.append(_issue("DISCOVERY_RULE_FIELD", f"{key} 含规则字段", "探测记录不得写规则值"))
        url = str(record.get("url", ""))
        if not url.startswith(("http://", "https://")):
            issues.append(_issue("DISCOVERY_URL_INVALID", f"{key} URL 非法", "使用实测 http(s) URL"))
        if url in seen_urls:
            issues.append(_issue("DISCOVERY_DUPLICATE_URL", f"同轮 URL 重复：{url}", "每 URL 只保留一条"))
        seen_urls.add(url)
        status = record.get("status")
        if status is not None and int(status) not in (200, 403, 404, 429):
            issues.append(_issue("DISCOVERY_STATUS_INVALID", f"{key} 状态非法：{status}", "使用 200/403/404/429/null"))
        if status == 200 and int(record.get("bytes_read") or 0) <= 0:
            issues.append(_issue("DISCOVERY_NO_BODY", f"{key} 200 但无响应体", "确认实测记录"))
        if status is None and not str(record.get("error") or "").strip():
            issues.append(_issue("DISCOVERY_NO_RESULT", f"{key} 既无状态也无错误", "确认实测记录"))
    return issues


def summarize(records: List[Dict[str, Any]], discovery_keys: Tuple[str, ...]) -> Dict[str, Any]:
    by_level = {level: 0 for level in DISCOVERY_LEVELS}
    objects: Dict[str, str] = {}
    for record in records:
        level = grade(record, discovery_keys)
        by_level[level] += 1
        key = str(record.get("key", ""))
        priority = {"failed_unreachable": 0, "no_evidence": 1, "candidate_rules": 2, "candidate_skill": 3, "discovery_source": 4}
        if key not in objects or priority[level] > priority[objects[key]]:
            objects[key] = level
    ok = sum(1 for record in records if record.get("status") == 200)
    failed = len(records) - ok
    summary = {
        "probed": len(records),
        "ok": ok,
        "failed": failed,
        "skill_md": by_level["candidate_skill"],
        "rules": by_level["candidate_rules"],
        "discovery": by_level["discovery_source"],
        "no_evidence": by_level["no_evidence"],
        "by_level": by_level,
        "objects": objects,
    }
    summary["equations"] = {
        "ok_eq_parts": ok == summary["skill_md"] + summary["rules"] + summary["discovery"] + summary["no_evidence"],
        "probed_eq_ok_failed": len(records) == ok + failed,
    }
    return summary


def load_round(path: str) -> Optional[DiscoveryResult]:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        return DiscoveryResult(None, [], [_issue("DISCOVERY_CORRUPT", f"探测记录损坏：{exc}", "恢复记录后重试")])
    records = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return DiscoveryResult(None, [], [_issue("DISCOVERY_CORRUPT", "candidates 不是数组", "修复记录")])
    discovery_keys, meta_present = _meta_for(path)
    issues = _validate_records(records)
    if not meta_present:
        issues.append(_issue("KIND_MISSING", "缺少探测元数据旁注，discovery_source 回落 candidate_rules", "补充 <round>.meta.json"))
    levels: Dict[str, set] = {}
    for record in records:
        key = str(record.get("key", ""))
        levels.setdefault(key, set()).add(grade(record, tuple(discovery_keys)))
    for key, values in levels.items():
        if len(values) > 1:
            issues.append(
                _issue("DUPLICATE_EVIDENCE_LEVEL", f"{key} 同一对象出现多个证据级别", "保留最高级别并记录说明", key)
            )
    summary = summarize(records, tuple(discovery_keys))
    summary["round"] = _round_name(path)
    summary["generated_at"] = payload.get("generated_at")
    summary["meta_present"] = meta_present
    summary["record_path"] = "platforms/discovery/" + os.path.basename(path)
    if not all(summary["equations"].values()):
        issues.append(_issue("DISCOVERY_COUNT_MISMATCH", "探测计数等式不成立", "重算记录", severity="error"))
    for issue in issues:
        if issue["code"] in ("DISCOVERY_COUNT_MISMATCH", "DISCOVERY_CORRUPT"):
            issue["severity"] = "error"
    return DiscoveryResult(summary, records, issues, _round_name(path))


def _round_name(path: str) -> str:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(path))
    return match.group(1) if match else os.path.splitext(os.path.basename(path))[0]


def load_latest(directory: str) -> Optional[DiscoveryResult]:
    if not os.path.isdir(directory):
        return None
    candidates = []
    for name in os.listdir(directory):
        if not name.endswith(".json") or name.endswith(".meta.json") or name.startswith("summary-"):
            continue
        match = re.search(r"(\d{4}-\d{2}-\d{2})", name)
        if match:
            candidates.append((match.group(1), os.path.join(directory, name)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return load_round(candidates[-1][1])