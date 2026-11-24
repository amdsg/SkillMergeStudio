"""Manifest parsing: four fields, strict unknown, no inference from repo metadata."""
from __future__ import annotations

import json
import re
from pathlib import Path

from agent.http.errors import DomainError

FIELDS = ("native_targets", "capability_tags", "version", "dependencies")
UNKNOWN = "unknown"
FM = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
MANIFEST_NAMES = ("skill.json", "manifest.json")


def _frontmatter(text: str) -> dict | None:
    match = FM.search(text)
    if not match:
        return None
    data = {}
    current = None
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current:
            item = stripped[2:].strip()
            if ":" in item:
                key, value = item.split(":", 1)
                data[current].append({key.strip(): value.strip().strip("'\"")})
            else:
                data[current].append(item.strip("'\""))
            continue
        if ":" not in line or line.startswith((" ", "\t")):
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            data[key] = [item.strip().strip("'\"") for item in value[1:-1].split(",") if item.strip()]
            current = None
        elif value:
            data[key] = value.strip("'\"")
            current = None
        else:
            data[key] = []
            current = key
    return data


def _normalize(key: str, value):
    if isinstance(value, str):
        value = value.strip()
    if key in ("native_targets", "capability_tags", "dependencies"):
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",") if part.strip()]
        if not isinstance(value, list):
            return UNKNOWN
        if key == "dependencies":
            normalized = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    normalized.append({"repo": item.strip(), "ref": "unknown"})
                elif isinstance(item, dict) and item.get("repo"):
                    normalized.append({"repo": str(item["repo"]), "ref": str(item.get("ref") or "unknown")})
            return normalized
        return [str(item) for item in value]
    if isinstance(value, list):
        return UNKNOWN
    return str(value)


def parse_text(text: str) -> dict:
    raw = _frontmatter(text)
    if raw is None:
        stripped = text.lstrip()
        if stripped.startswith("{"):
            try:
                raw = json.loads(text)
            except ValueError:
                raw = None
    if not isinstance(raw, dict):
        return {
            "parse_status": "failed",
            "fields": {field: UNKNOWN for field in FIELDS},
            "unknown_fields": list(FIELDS),
        }
    fields = {}
    unknown_fields = []
    for field in FIELDS:
        value = _normalize(field, raw.get(field, None))
        if value == UNKNOWN or value is None or value == "":
            fields[field] = UNKNOWN
            unknown_fields.append(field)
        else:
            fields[field] = value
    status = "ok" if not unknown_fields else "partial"
    return {"parse_status": status, "fields": fields, "unknown_fields": unknown_fields}


def locate(path: Path) -> Path:
    if path.is_dir():
        for name in MANIFEST_NAMES:
            candidate = path / name
            if candidate.is_file():
                return candidate
        return path / "SKILL.md"
    return path


def parse_file(path: Path, source_commit: str) -> dict:
    if not str(source_commit or "").strip() or str(source_commit) == UNKNOWN:
        raise DomainError("E_REF_INCOMPLETE", "wb.error.ref_incomplete",
                          params={"field": "source_commit", "expected": "commit sha", "actual": source_commit},
                          fix_key="wb.fix.redownload_source")
    entry = locate(path)
    if not entry.is_file():
        return {
            "source_path": path.as_posix(),
            "source_commit": source_commit,
            "parse_status": "failed",
            "fields": {field: UNKNOWN for field in FIELDS},
            "unknown_fields": list(FIELDS),
        }
    text = entry.read_text(encoding="utf-8", errors="replace")
    result = parse_text(text)
    result.update({"source_path": path.as_posix(), "source_commit": source_commit})
    return result