"""Local library index: ten fields, rebuildable, consistency-checked, no overwrite."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from agent.core.hashing import sha256_text

FIELDS = (
    "skill_id", "name", "source_repo", "source_commit", "native_targets",
    "capability_tags", "version", "manifest_status", "entry_path", "indexed_at",
)
UNKNOWN = "unknown"


def entry_id(name: str, commit: str) -> str:
    return sha256_text(f"{name}|{commit}")[:16]


def unique_dir(base: Path, name: str) -> Path:
    candidate = base / name
    if not candidate.exists():
        return candidate
    for index in range(2, 100):
        candidate = base / f"{name}_{index}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(name)


def build_entry(skill_id: str, name: str, repo: str, commit: str, manifest: dict, entry_path: str) -> dict:
    fields = manifest.get("fields") or {}
    return {
        "skill_id": skill_id,
        "name": name,
        "source_repo": repo,
        "source_commit": commit,
        "native_targets": fields.get("native_targets", UNKNOWN),
        "capability_tags": fields.get("capability_tags", UNKNOWN),
        "version": fields.get("version", UNKNOWN),
        "manifest_status": manifest.get("parse_status", "failed"),
        "entry_path": entry_path,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }


def write_entry(index_dir: Path, entry: dict) -> Path:
    missing = [field for field in FIELDS if field not in entry]
    if missing:
        raise ValueError(f"index entry missing {missing}")
    index_dir.mkdir(parents=True, exist_ok=True)
    path = index_dir / "index-v1.jsonl"
    tmp = path.with_suffix(".jsonl.tmp")
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    tmp.write_text(existing + json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


def read_index(index_dir: Path) -> list[dict]:
    path = index_dir / "index-v1.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def rebuild_from_disk(entries_dir: Path, index_dir: Path) -> list[dict]:
    rebuilt = []
    for folder in sorted(entries_dir.glob("*")) if entries_dir.is_dir() else []:
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            continue
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        entry = data.get("index_entry")
        if isinstance(entry, dict):
            rebuilt.append(entry)
    index_dir.mkdir(parents=True, exist_ok=True)
    path = index_dir / "index-v1.jsonl"
    tmp = path.with_suffix(".jsonl.tmp")
    tmp.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rebuilt), encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return rebuilt


def verify(index_dir: Path, entries_dir: Path) -> dict:
    indexed = {row.get("skill_id"): row for row in read_index(index_dir)}
    on_disk = set()
    if entries_dir.is_dir():
        for folder in entries_dir.glob("*"):
            manifest_path = folder / "manifest.json"
            if manifest_path.is_file():
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                entry = data.get("index_entry") or {}
                if entry.get("skill_id"):
                    on_disk.add(entry["skill_id"])
    missing = sorted(set(indexed) - on_disk)
    extra = sorted(on_disk - set(indexed))
    return {"ok": not missing and not extra, "missing_on_disk": missing, "missing_in_index": extra}