"""Reverse-order rollback. Never deletes files that were not created by this transaction."""
from __future__ import annotations

import shutil
from pathlib import Path

from agent.core.hashing import sha256_file


def rollback(manifest: dict, target_dir: Path, created_hashes: dict[str, str] | None = None) -> dict:
    created_hashes = created_hashes or {}
    backup_dir = Path(manifest.get("backup_dir", "")) if manifest.get("backup_dir") else None
    restored = []
    removed = []
    errors = []
    for entry in reversed(manifest.get("files", [])):
        relative = entry.get("path", "")
        target = target_dir / relative
        try:
            if entry.get("existed"):
                if backup_dir is None:
                    errors.append({"path": relative, "reason": "backup_dir_missing"})
                    continue
                source = backup_dir / "files" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_suffix(target.suffix + ".tmp")
                shutil.copy2(source, tmp)
                tmp.replace(target)
                if sha256_file(target) != entry.get("backup_sha256"):
                    errors.append({"path": relative, "reason": "restore_hash_mismatch"})
                else:
                    restored.append(relative)
            else:
                if target.is_file():
                    expected = created_hashes.get(relative)
                    if expected is None or sha256_file(target) != expected:
                        errors.append({"path": relative, "reason": "unplanned_file_not_removed"})
                        continue
                    target.unlink()
                    removed.append(relative)
        except OSError as error:
            errors.append({"path": relative, "reason": str(error)[:120]})
    return {"ok": not errors, "restored": restored, "removed": removed, "errors": errors}