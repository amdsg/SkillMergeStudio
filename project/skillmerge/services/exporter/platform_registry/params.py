from __future__ import annotations

from typing import Any, Dict, Optional

from ....util.errors import DomainError


def _bool(value: Any, name: str) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if str(value).lower() in ("true", "1"):
        return True
    if str(value).lower() in ("false", "0"):
        return False
    raise DomainError("INVALID_ARGUMENT", f"{name} 必须是 true 或 false", "使用 verified=true/false")


def _int(value: Any, name: str, minimum: int, maximum: int, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise DomainError("INVALID_ARGUMENT", f"{name} 必须是整数", f"范围 {minimum}–{maximum}")
    if number < minimum or number > maximum:
        raise DomainError("INVALID_ARGUMENT", f"{name} 超出范围", f"范围 {minimum}–{maximum}")
    return number


def validate_platform_params(data: Dict[str, Any], registry) -> Dict[str, Any]:
    schema = registry.result.schema
    groups = schema["enums"]["group"]
    kinds = schema["enums"]["kind"]
    evidence = schema["enums"]["evidence_level"]
    kind = str(data.get("kind") or "")
    if kind and kind not in kinds:
        raise DomainError("INVALID_ARGUMENT", f"未知 kind：{kind}", f"使用 {kinds}")
    group = str(data.get("group") or "")
    if group and group not in groups:
        raise DomainError("INVALID_ARGUMENT", f"未知 group：{group}", f"使用 {groups}")
    evidence_value = str(data.get("evidence") or "")
    if evidence_value and evidence_value not in evidence:
        raise DomainError("INVALID_ARGUMENT", f"未知 evidence：{evidence_value}", f"使用 {evidence}")
    q = str(data.get("q") or "")
    if len(q) > 100:
        raise DomainError("INVALID_ARGUMENT", "q 超过 100 字符", "缩短搜索词")
    sort = str(data.get("sort") or "status")
    if sort not in ("status", "group", "label"):
        raise DomainError("INVALID_ARGUMENT", f"未知排序：{sort}", "使用 status/group/label")
    return {
        "kind": kind,
        "group": group,
        "verified": _bool(data.get("verified"), "verified"),
        "evidence": evidence_value,
        "q": q,
        "sort": sort,
        "limit": _int(data.get("limit"), "limit", 0, 1000, 0),
        "offset": _int(data.get("offset"), "offset", 0, 1000000, 0),
    }