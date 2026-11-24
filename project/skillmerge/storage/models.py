from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_loads(raw: Any, fallback: Any) -> Any:
    if raw is None or raw == "":
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


@dataclass
class Skill:
    id: str
    path: str
    real_path: str
    name: str = ""
    description: str = ""
    body_preview: str = ""
    search_blob: str = ""
    frontmatter_json: str = "{}"
    headings_json: str = "[]"
    resources_json: str = "[]"
    dependencies_json: str = "[]"
    warnings_json: str = "[]"
    category: str = "未分类"
    category_source: str = "keyword"
    confidence: float = 0.0
    platform_origin: str = "unknown"
    size_bytes: int = 0
    lines: int = 0
    chars: int = 0
    mtime: float = 0.0
    content_hash: str = ""
    quality_score: int = 0
    quality_json: str = "[]"
    parse_error: Optional[str] = None
    missing: int = 0
    first_seen: str = ""
    last_seen: str = ""

    def to_row(self) -> Dict[str, Any]:
        row = {}
        for item in fields(self):
            row[item.name] = getattr(self, item.name)
        return row

    @classmethod
    def from_row(cls, row: Any) -> "Skill":
        data = dict(row)
        return cls(**{k: v for k, v in data.items() if k in {f.name for f in fields(cls)}})

    def frontmatter(self) -> Dict[str, Any]:
        value = _json_loads(self.frontmatter_json, {})
        return value if isinstance(value, dict) else {}

    def headings(self) -> List[Dict[str, Any]]:
        value = _json_loads(self.headings_json, [])
        return value if isinstance(value, list) else []

    def resources(self) -> List[Dict[str, Any]]:
        value = _json_loads(self.resources_json, [])
        return value if isinstance(value, list) else []

    def dependencies(self) -> List[Dict[str, Any]]:
        value = _json_loads(self.dependencies_json, [])
        return value if isinstance(value, list) else []

    def warnings(self) -> List[Dict[str, Any]]:
        value = _json_loads(self.warnings_json, [])
        return value if isinstance(value, list) else []


@dataclass
class SkillLocation:
    skill_id: str
    path: str
    real_path: str
    platform: str = "unknown"
    is_primary: int = 0
    mtime: float = 0.0
    size_bytes: int = 0
    last_seen: str = ""

    def to_row(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class ScanStats:
    found: int = 0
    new: int = 0
    updated: int = 0
    skipped_permission: int = 0
    pruned: int = 0
    dup_locations: int = 0
    limit_hit: bool = False
    time_limit_hit: bool = False
    body_reads: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScanStats":
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (data or {}).items() if k in allowed})


@dataclass
class Scan:
    id: Optional[int]
    mode: str
    roots_json: str
    started_at: str
    finished_at: Optional[str] = None
    job_id: Optional[str] = None
    stats_json: str = "{}"
    coverage_json: str = "[]"

    def to_row(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name != "id"}


@dataclass
class Job:
    id: str
    type: str
    status: str
    params_json: str
    progress_json: str = "{}"
    result_json: Optional[str] = None
    error_json: Optional[str] = None
    cancel_requested: int = 0
    cancel_reason: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: Any) -> "Job":
        data = dict(row)
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def params(self) -> Dict[str, Any]:
        value = _json_loads(self.params_json, {})
        return value if isinstance(value, dict) else {}

    def progress(self) -> Dict[str, Any]:
        value = _json_loads(self.progress_json, {})
        return value if isinstance(value, dict) else {}

    def result(self) -> Any:
        return _json_loads(self.result_json, None)

    def error(self) -> Optional[Dict[str, Any]]:
        value = _json_loads(self.error_json, None)
        return value if isinstance(value, dict) else None


@dataclass
class JobEvent:
    job_id: str
    seq: int
    phase: str
    current: int = 0
    total: Optional[int] = None
    message: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}


@dataclass
class Artifact:
    id: str
    name: str
    slug: str
    platform: str
    kind: str
    dir_path: str
    sha256: str
    manifest_json: str
    created_at: str
    size_bytes: int = 0
    zip_path: Optional[str] = None
    installed_path: Optional[str] = None
    plan_summary_json: str = "{}"
    status: str = "active"
    trash_path: Optional[str] = None
    undone_at: Optional[str] = None
    job_id: Optional[str] = None

    def to_row(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_row(cls, row: Any) -> "Artifact":
        data = dict(row)
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in allowed})

    def manifest(self) -> Dict[str, Any]:
        value = _json_loads(self.manifest_json, {})
        return value if isinstance(value, dict) else {}


@dataclass
class MergeSource:
    artifact_id: str
    skill_id: str
    source_hash: str
    path: str


def dumps(value: Any) -> str:
    return _json_dumps(value)


def loads(raw: Any, fallback: Any = None) -> Any:
    return _json_loads(raw, fallback)