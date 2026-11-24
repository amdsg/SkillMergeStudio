from __future__ import annotations

from typing import Dict, List, Tuple

from . import defaults


def migrate(raw: Dict[str, object]) -> Tuple[Dict[str, object], List[Dict[str, str]]]:
    warnings: List[Dict[str, str]] = []
    data = dict(raw)
    version = int(data.get("config_version") or 0)
    if version > defaults.CONFIG_VERSION:
        warnings.append(
            {
                "code": "CONFIG_VERSION_NEWER",
                "level": "warn",
                "message": f"配置版本 {version} 高于程序支持的 {defaults.CONFIG_VERSION}",
                "fix": "升级 Skill Merge Studio 或手动备份后重建配置",
            }
        )
        return data, warnings
    if version < 1:
        data = _v0_to_v1(data)
        version = 1
        warnings.append({"code": "CONFIG_MIGRATED", "level": "info", "message": "配置已迁移到 v1", "fix": ""})
    if version < 2:
        data = _v1_to_v2(data)
        version = 2
        warnings.append({"code": "CONFIG_MIGRATED", "level": "info", "message": "配置已迁移到 v2", "fix": ""})
    data["config_version"] = version
    return data, warnings


def _v0_to_v1(raw: Dict[str, object]) -> Dict[str, object]:
    data = dict(raw)
    if not data.get("categories"):
        data["categories"] = [dict(item) for item in defaults.DEFAULT_CATEGORIES]
    if not data.get("slug_map"):
        data["slug_map"] = dict(defaults.DEFAULT_SLUG_MAP)
    if not data.get("ignore_rules"):
        data["ignore_rules"] = list(defaults.DEFAULT_IGNORE_RULES)
    return data


def _v1_to_v2(raw: Dict[str, object]) -> Dict[str, object]:
    data = dict(raw)
    ai = dict(data.get("ai") or {})
    ai.setdefault("timeout", 90)
    ai.setdefault("enabled", False)
    ai.setdefault("base_url", "")
    ai.setdefault("model", "")
    data["ai"] = ai
    data.setdefault("trash", {"retain_days": defaults.TRASH_RETAIN_DAYS, "max_gb": defaults.TRASH_MAX_GB})
    data.setdefault("language", defaults.DEFAULT_LANGUAGE)
    return data