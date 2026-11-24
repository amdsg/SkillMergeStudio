from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class AIConfig:
    enabled: bool = False
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    timeout: int = 90

    def public(self) -> Dict[str, object]:
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout,
            "api_key_set": bool(self.api_key),
        }


@dataclass(frozen=True)
class AppConfig:
    config_version: int
    data_dir: str
    roots: Tuple[str, ...] = ()
    save_dir: str = ""
    ignore_rules: Tuple[str, ...] = ()
    categories: Tuple[Dict[str, str], ...] = ()
    slug_map: Dict[str, str] = field(default_factory=dict)
    scan_depth: int = 10
    scan_limit: int = 4000
    scan_time_limit: int = 150
    ai: AIConfig = field(default_factory=AIConfig)
    trash_retain_days: int = 30
    trash_max_gb: int = 2
    language: str = "zh"

    def with_changes(self, **changes) -> "AppConfig":
        data = {
            "config_version": self.config_version,
            "data_dir": self.data_dir,
            "roots": self.roots,
            "save_dir": self.save_dir,
            "ignore_rules": self.ignore_rules,
            "categories": self.categories,
            "slug_map": self.slug_map,
            "scan_depth": self.scan_depth,
            "scan_limit": self.scan_limit,
            "scan_time_limit": self.scan_time_limit,
            "ai": self.ai,
            "trash_retain_days": self.trash_retain_days,
            "trash_max_gb": self.trash_max_gb,
            "language": self.language,
        }
        data.update(changes)
        return AppConfig(**data)

    def public(self, warnings: List[Dict[str, str]] = None) -> Dict[str, object]:
        return {
            "config_version": self.config_version,
            "roots": list(self.roots),
            "save_dir": self.save_dir,
            "data_dir": self.data_dir,
            "ignore_rules": list(self.ignore_rules),
            "categories": [dict(item) for item in self.categories],
            "slug_map": dict(self.slug_map),
            "scan_depth": self.scan_depth,
            "scan_limit": self.scan_limit,
            "scan_time_limit": self.scan_time_limit,
            "ai": self.ai.public(),
            "trash": {"retain_days": self.trash_retain_days, "max_gb": self.trash_max_gb},
            "language": self.language,
            "warnings": warnings or [],
        }