"""Backup manifest and copy/verify helpers."""
from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agent.core.hashing import sha256_file


def create(backup_root: Path, target_dir: Path, files: list[str]) -> dict:
    backup_id = uuid.uuid4().hex[:12]
    backup_dir = backup_root / backup_id
    entries = []
    for relative in files:
        source = target_dir / relative
        exists = source.is_file()
        entry = {"path": relative, "existed": exists}
        if exists:
            copy = backup_dir / "files" / relative
            copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, copy)
            entry["backup_sha256"] = sha256_file(source)
            entry["size"] = source.stat().st_size
            if sha256_file(copy) != entry["backup_sha256"]:
                raise OSError(f"backup verification failed: {relative}")
        entries.append(entry)
    manifest = {
        "backup_id": backup_id,
        "backup_dir": backup_dir.as_posix(),
        "target_dir": target_dir.as_posix(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": entries,
    }
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    return manifest


def verify(manifest: dict) -> list[str]:
    problems = []
    backup_dir = Path(manifest.get("target_dir", ""))
    for entry in manifest.get("files", []):
        if not entry.get("existed"):
            continue
        copy = Path(manifest.get("backup_dir", "")) if manifest.get("backup_dir") else None
        if copy is None:
            continue
        path = copy / "files" / entry["path"]
        if not path.is_file() or sha256_file(path) != entry.get("backup_sha256"):
            problems.append(entry["path"])
    return problems