from __future__ import annotations

from typing import Any, Dict, List

from ..util.errors import DomainError

DEFAULT_PAGE_SIZE = 50
MAX_LIST_LIMIT = 500


def _int_value(value: Any, name: str, minimum: int, maximum: int, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise DomainError("INVALID_ARGUMENT", f"{name} 必须是整数", f"将 {name} 设为 {minimum}–{maximum} 的整数")
    if number < minimum or number > maximum:
        raise DomainError("INVALID_ARGUMENT", f"{name} 超出范围 {minimum}–{maximum}", f"将 {name} 调整为范围内的值")
    return number


def _bool_value(value: Any, name: str, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise DomainError("INVALID_ARGUMENT", f"{name} 必须是布尔值", f"将 {name} 设为 true 或 false")


def _roots(value: Any, name: str, maximum: int = 50) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > maximum:
        raise DomainError("INVALID_ARGUMENT", f"{name} 必须是 1–{maximum} 项的数组", f"传入路径数组，最多 {maximum} 项")
    result = [str(item).strip() for item in value if str(item).strip()]
    if len(result) != len(value):
        raise DomainError("INVALID_ARGUMENT", f"{name} 含空路径", "删除空字符串后重试")
    return result


def scan_params(payload: Dict[str, Any], config, full: bool = False) -> Dict[str, Any]:
    data = payload or {}
    roots = _roots(data.get("roots") if not full else data.get("drives"), "roots" if not full else "drives")
    return {
        "roots": roots,
        "mode": "full" if full else "probe",
        "depth": _int_value(data.get("depth"), "depth", 1, 30, config.scan_depth),
        "limit": _int_value(data.get("limit"), "limit", 1, 20000, config.scan_limit),
        "time_limit": _int_value(data.get("time_limit"), "time_limit", 1, 3600, config.scan_time_limit),
        "refresh": _bool_value(data.get("refresh"), "refresh", False),
        "include_removable": _bool_value(data.get("include_removable"), "include_removable", False),
        "include_network": _bool_value(data.get("include_network"), "include_network", False),
    }


STRATEGIES = ("keep-all", "prefer-first", "prefer-largest", "manual")
ACTIONS = ("keepA", "keepB", "keepBoth", "manual")


def _decisions(value: Any) -> Dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(key): str(action) for key, action in value.items() if str(action) in ACTIONS}
    if isinstance(value, list):
        result = {}
        for item in value:
            if isinstance(item, dict) and str(item.get("action")) in ACTIONS:
                result[str(item.get("key", ""))] = str(item["action"])
        return result
    raise DomainError("INVALID_ARGUMENT", "decisions 必须是对象或数组", "传入 {key,action} 数组")


def merge_params(payload: Dict[str, Any], config) -> Dict[str, Any]:
    data = payload or {}
    name = str(data.get("name") or "").strip()
    if not name or len(name) > 120:
        raise DomainError("INVALID_ARGUMENT", "name 必须为 1–120 字符", "填写产物名称")
    sources = _roots(data.get("sources"), "sources", maximum=50)
    if not sources:
        raise DomainError("INVALID_ARGUMENT", "sources 不能为空", "至少选择一个技能")
    deduped = []
    seen = set()
    for source in sources:
        if source not in seen:
            seen.add(source)
            deduped.append(source)
    strategy = str(data.get("strategy") or "keep-all")
    if strategy not in STRATEGIES:
        raise DomainError("INVALID_ARGUMENT", f"未知策略：{strategy}", "使用 keep-all/prefer-first/prefer-largest/manual")
    aliases = data.get("aliases") or []
    if not isinstance(aliases, list):
        raise DomainError("INVALID_ARGUMENT", "aliases 必须是数组", "传入 [{from,to}]")
    use_ai = _bool_value(data.get("use_ai"), "use_ai", False)
    confirm_ai = _bool_value(data.get("confirm_ai"), "confirm_ai", False)
    if use_ai and not confirm_ai:
        raise DomainError("AI_NOT_CONFIRMED", "发送技能正文给 AI 前必须确认", "传 confirm_ai=true", 400)
    confirm_keys = data.get("ai_confirm_keys") or []
    if not isinstance(confirm_keys, list) or len(confirm_keys) > 200:
        raise DomainError("INVALID_ARGUMENT", "ai_confirm_keys 必须是 ≤200 项的数组", "传入确认的章节 key 数组")
    return {
        "sources": deduped,
        "name": name,
        "strategy": strategy,
        "platform": str(data.get("platform") or "generic"),
        "save_dir": str(data.get("save_dir") or ""),
        "copy_assets": _bool_value(data.get("copy_assets"), "copy_assets", True),
        "use_ai": use_ai,
        "confirm_ai": confirm_ai,
        "ai_confirm_keys": [str(item) for item in confirm_keys if str(item).strip()],
        "description": str(data.get("description") or ""),
        "decisions": _decisions(data.get("decisions")),
        "aliases": [
            {"from": str(item.get("from", "")), "to": str(item.get("to", ""))}
            for item in aliases
            if isinstance(item, dict)
        ],
    }


EXPORT_MODES = ("dir", "zip", "install", "download")
LENGTH_MODES = ("full", "compact", "minimal")
PROFILES = ("claude", "gpt", "gemini", "qwen", "kimi", "doubao", "deepseek", "generic")
MAX_BATCH_PLATFORMS = 28


def _platform_list(value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise DomainError("INVALID_ARGUMENT", "platforms 必须是数组", "传入平台 id 数组")
    result: List[str] = []
    seen = set()
    for item in value:
        if not isinstance(item, str):
            raise DomainError("INVALID_ARGUMENT", "platforms 元素必须是字符串", "传入平台 id 数组")
        platform = item.strip()
        if platform and platform not in seen:
            seen.add(platform)
            result.append(platform)
    if not result:
        raise DomainError("EXPORT_BATCH_EMPTY", "platforms 不能为空", "选择至少一个平台后重试", 400)
    if len(result) > MAX_BATCH_PLATFORMS:
        raise DomainError(
            "EXPORT_BATCH_TOO_LARGE",
            "一次最多导出 %d 个平台" % MAX_BATCH_PLATFORMS,
            "减少平台数量后重试",
            400,
            {"max": MAX_BATCH_PLATFORMS, "requested": len(result)},
        )
    return result


def export_params(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload or {}
    artifact_id = str(data.get("artifact_id") or "").strip()
    if not artifact_id:
        raise DomainError("INVALID_ARGUMENT", "artifact_id 不能为空", "先完成合并并取得产物 id")
    platforms = _platform_list(data.get("platforms"))
    platform = str(data.get("platform") or "").strip()
    platform = platforms[0] if platforms else (platform or "generic")
    mode = str(data.get("mode") or "dir")
    if mode not in EXPORT_MODES:
        raise DomainError("INVALID_ARGUMENT", f"未知导出模式：{mode}", "使用 dir/zip/install/download")
    length_mode = str(data.get("length_mode") or "full")
    if length_mode not in LENGTH_MODES:
        raise DomainError("INVALID_ARGUMENT", f"未知篇幅：{length_mode}", "使用 full/compact/minimal")
    profile = str(data.get("profile") or "generic")
    if profile not in PROFILES:
        raise DomainError("INVALID_ARGUMENT", f"未知风格：{profile}", "使用 8 种预设之一")
    scope = str(data.get("install_scope") or "global")
    if scope not in ("global", "project"):
        raise DomainError("INVALID_ARGUMENT", "install_scope 必须是 global 或 project", "选择安装范围")
    name_en = str(data.get("name_en") or "").strip()
    if len(name_en) > 120:
        raise DomainError("INVALID_ARGUMENT", "name_en 过长", "缩短英文名")
    return {
        "artifact_id": artifact_id,
        "platform": platform,
        "platforms": platforms,
        "mode": mode,
        "install_scope": scope,
        "length_mode": length_mode,
        "profile": profile,
        "examples": _bool_value(data.get("examples"), "examples", False),
        "name_en": name_en,
        "confirm_candidate": _bool_value(data.get("confirm_candidate"), "confirm_candidate", False),
    }


def export_preview_params(payload: Dict[str, Any]) -> Dict[str, Any]:
    return export_params(payload)


def classify_params(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload or {}
    ids = data.get("skill_ids")
    if ids is not None:
        if not isinstance(ids, list) or len(ids) > 500:
            raise DomainError("INVALID_ARGUMENT", "skill_ids 必须是 ≤500 项的数组", "传入技能 id 数组或省略表示全部")
        ids = [str(item).strip() for item in ids if str(item).strip()]
        if not ids:
            ids = None
    use_ai = _bool_value(data.get("use_ai"), "use_ai", False)
    confirm_ai = _bool_value(data.get("confirm_ai"), "confirm_ai", False)
    if use_ai and not confirm_ai:
        raise DomainError("AI_NOT_CONFIRMED", "发送技能文本给 AI 前必须确认", "传 confirm_ai=true", 400)
    return {"skill_ids": ids, "use_ai": use_ai, "confirm_ai": confirm_ai}


def page_args(request, default_limit: int = DEFAULT_PAGE_SIZE):
    limit = _int_value(request.q("limit", ""), "limit", 1, MAX_LIST_LIMIT, default_limit)
    offset = _int_value(request.q("offset", ""), "offset", 0, 1000000, 0)
    return limit, offset


def skill_list_filters(request) -> Dict[str, Any]:
    filters: Dict[str, Any] = {
        "category": request.q("category", ""),
        "platform": request.q("platform", ""),
        "q": request.q("q", "")[:200],
        "duplicate": request.q("duplicate", ""),
        "include_missing": request.q("include_missing", "") in ("1", "true"),
    }
    if request.q("quality_min", "") != "":
        filters["quality_min"] = _int_value(request.q("quality_min"), "quality_min", 0, 100, 0)
    if request.q("quality_max", "") != "":
        filters["quality_max"] = _int_value(request.q("quality_max"), "quality_max", 0, 100, 100)
    if request.q("has_resources", "") in ("1", "true"):
        filters["has_resources"] = True
    if request.q("parse_error", "") in ("1", "true"):
        filters["parse_error"] = True
    if request.q("size_min", "") != "":
        filters["size_min"] = _int_value(request.q("size_min"), "size_min", 0, 10**9, 0)
    if request.q("size_max", "") != "":
        filters["size_max"] = _int_value(request.q("size_max"), "size_max", 0, 10**9, 10**9)
    if request.q("mtime_from", "") != "":
        filters["mtime_from"] = float(request.q("mtime_from"))
    sort = request.q("sort", "name")
    if sort not in ("name", "quality", "size", "mtime"):
        raise DomainError("INVALID_ARGUMENT", "sort 必须是 name/quality/size/mtime", "修正排序参数")
    filters["sort"] = sort
    return filters