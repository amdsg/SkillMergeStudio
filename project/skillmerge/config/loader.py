from __future__ import annotations

import json
import os
from typing import Dict, List, Tuple

from . import defaults
from . import paths

API_KEY_ENV = "SKILLMERGE_API_KEY"


def _warn(code: str, message: str, fix: str = "") -> Dict[str, str]:
    return {"code": code, "level": "warn", "message": message, "fix": fix}


def _read_raw(path: str, warnings: List[Dict[str, str]]) -> Dict[str, object]:
    if not os.path.isfile(path):
        return defaults.default_config_dict()
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            raise ValueError("config root must be an object")
        return raw
    except (OSError, ValueError) as exc:
        backup = path + ".bak"
        try:
            if os.path.isfile(path):
                os.replace(path, backup)
        except OSError:
            pass
        warnings.append(_warn("CONFIG_CORRUPT", f"配置文件损坏，已使用默认配置：{exc}", "检查 config.json 或从 .bak 恢复"))
        return defaults.default_config_dict()


def _merge_defaults(raw: Dict[str, object]) -> Dict[str, object]:
    merged = defaults.default_config_dict()
    for key, value in raw.items():
        if key == "ai" and isinstance(value, dict):
            ai = dict(merged["ai"])
            ai.update(value)
            merged["ai"] = ai
        elif key == "trash" and isinstance(value, dict):
            trash = dict(merged["trash"])
            trash.update(value)
            merged["trash"] = trash
        else:
            merged[key] = value
    return merged


def _normalize(raw: Dict[str, object], dd: str, warnings: List[Dict[str, str]]) -> Dict[str, object]:
    raw["config_version"] = int(raw.get("config_version", defaults.CONFIG_VERSION))
    roots = raw.get("roots") or []
    if not isinstance(roots, list):
        roots = []
        warnings.append(_warn("CONFIG_ROOTS_INVALID", "roots 不是数组，已忽略", "将 roots 设为路径数组"))
    raw["roots"] = [paths.expand_path(str(item)) for item in roots if str(item).strip()]
    save_dir = str(raw.get("save_dir") or "")
    raw["save_dir"] = paths.expand_path(save_dir, dd) if save_dir else paths.default_save_dir(dd)
    try:
        raw["scan_depth"] = max(1, min(30, int(raw.get("scan_depth", defaults.DEFAULT_SCAN_DEPTH))))
        raw["scan_limit"] = max(1, min(20000, int(raw.get("scan_limit", defaults.DEFAULT_SCAN_LIMIT))))
        raw["scan_time_limit"] = max(1, min(3600, int(raw.get("scan_time_limit", defaults.DEFAULT_SCAN_TIME_LIMIT))))
    except (TypeError, ValueError):
        raw["scan_depth"] = defaults.DEFAULT_SCAN_DEPTH
        raw["scan_limit"] = defaults.DEFAULT_SCAN_LIMIT
        raw["scan_time_limit"] = defaults.DEFAULT_SCAN_TIME_LIMIT
        warnings.append(_warn("CONFIG_RANGE_INVALID", "扫描参数不是整数，已回退默认值", "将 scan_depth 设为 1–30"))
    ignore = raw.get("ignore_rules") or []
    raw["ignore_rules"] = [str(item) for item in ignore] if isinstance(ignore, list) else list(defaults.DEFAULT_IGNORE_RULES)
    categories = raw.get("categories") or []
    if not isinstance(categories, list) or not categories:
        categories = [dict(item) for item in defaults.DEFAULT_CATEGORIES]
    raw["categories"] = [
        {"name": str(item.get("name", "")).strip(), "slug": str(item.get("slug", "")).strip()}
        for item in categories
        if isinstance(item, dict) and str(item.get("name", "")).strip()
    ]
    slug_map = raw.get("slug_map")
    if not isinstance(slug_map, dict) or not slug_map:
        slug_map = {item["name"]: item["slug"] for item in raw["categories"]}
    raw["slug_map"] = {str(k): str(v) for k, v in slug_map.items()}
    trash = raw.get("trash") if isinstance(raw.get("trash"), dict) else {}
    raw["trash"] = {
        "retain_days": int(trash.get("retain_days", defaults.TRASH_RETAIN_DAYS)),
        "max_gb": int(trash.get("max_gb", defaults.TRASH_MAX_GB)),
    }
    language = str(raw.get("language") or defaults.DEFAULT_LANGUAGE)
    raw["language"] = language if language in ("zh", "en") else "zh"
    return raw


def _apply_env(raw: Dict[str, object], env: Dict[str, str]) -> Tuple[Dict[str, object], Dict[str, str]]:
    sources = {"save_dir": "file", "api_key": "none"}
    if env.get(API_KEY_ENV):
        raw["ai"]["api_key"] = env[API_KEY_ENV]
        sources["api_key"] = "env"
    elif raw["ai"].get("api_key"):
        sources["api_key"] = "file"
    return raw, sources


def _build(raw: Dict[str, object], dd: str) -> "AppConfig":
    from . import AppConfig, AIConfig

    ai_raw = raw.get("ai") or {}
    ai = AIConfig(
        enabled=bool(ai_raw.get("enabled")),
        base_url=str(ai_raw.get("base_url") or ""),
        model=str(ai_raw.get("model") or ""),
        api_key=str(ai_raw.get("api_key") or ""),
        timeout=max(1, int(ai_raw.get("timeout") or 90)),
    )
    return AppConfig(
        config_version=int(raw.get("config_version", defaults.CONFIG_VERSION)),
        data_dir=dd,
        roots=tuple(raw.get("roots") or ()) if isinstance(raw.get("roots"), list) else tuple(raw.get("roots") or ()),
        save_dir=str(raw.get("save_dir")),
        ignore_rules=tuple(raw.get("ignore_rules") or ()),
        categories=tuple(raw.get("categories") or ()),
        slug_map=dict(raw.get("slug_map") or {}),
        scan_depth=int(raw.get("scan_depth", defaults.DEFAULT_SCAN_DEPTH)),
        scan_limit=int(raw.get("scan_limit", defaults.DEFAULT_SCAN_LIMIT)),
        scan_time_limit=int(raw.get("scan_time_limit", defaults.DEFAULT_SCAN_TIME_LIMIT)),
        ai=ai,
        trash_retain_days=int(raw["trash"]["retain_days"]),
        trash_max_gb=int(raw["trash"]["max_gb"]),
        language=str(raw.get("language", "zh")),
    )


def load_config(dd: str = None, env: Dict[str, str] = None) -> Tuple["AppConfig", List[Dict[str, str]]]:
    from .migrate import migrate

    directory = dd or paths.data_dir(env)
    os.makedirs(directory, exist_ok=True)
    warnings: List[Dict[str, str]] = []
    raw = _read_raw(paths.config_path(directory), warnings)
    raw, migrate_warnings = migrate(raw)
    warnings.extend(migrate_warnings)
    raw = _merge_defaults(raw)
    raw = _normalize(raw, directory, warnings)
    raw, _sources = _apply_env(raw, env if env is not None else os.environ)
    return _build(raw, directory), warnings


def save_config(dd: str, payload: Dict[str, object], env: Dict[str, str] = None) -> Tuple["AppConfig", List[Dict[str, str]]]:
    from .migrate import migrate

    directory = dd or paths.data_dir(env)
    os.makedirs(directory, exist_ok=True)
    warnings: List[Dict[str, str]] = []
    base = _read_raw(paths.config_path(directory), warnings)
    merged = _deep_merge(base, payload)
    merged, migrate_warnings = migrate(merged)
    warnings.extend(migrate_warnings)
    merged = _normalize(merged, directory, warnings)
    names = [item["name"] for item in merged["categories"]]
    slugs = [item["slug"] for item in merged["categories"]]
    if len(set(names)) != len(names) or len(set(slugs)) != len(slugs):
        from ..util.errors import DomainError

        raise DomainError("SLUG_CONFLICT", "分类名称或 slug 重复", "为每个分类设置唯一名称与 slug", 400)
    _atomic_write(paths.config_path(directory), merged)
    config, load_warnings = load_config(directory, env)
    warnings.extend(load_warnings)
    return config, warnings


def _deep_merge(base: Dict[str, object], patch: Dict[str, object]) -> Dict[str, object]:
    result = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            nested = dict(result[key])
            nested.update(value)
            result[key] = nested
        else:
            result[key] = value
    return result


def _atomic_write(path: str, raw: Dict[str, object]) -> None:
    tmp = path + ".tmp"
    payload = json.dumps(raw, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass