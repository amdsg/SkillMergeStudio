from __future__ import annotations

import os
import shutil
import threading
from typing import Any, Dict

from ..fsops import assert_inside, move_to_trash
from ...util.errors import DomainError
from ...util.timeutil import utc_now_iso
from .manifest import verify_manifest

LOCKS: Dict[str, threading.Lock] = {}
LOCK_GUARD = threading.Lock()


def _lock_for(artifact_id: str) -> threading.Lock:
    with LOCK_GUARD:
        return LOCKS.setdefault(artifact_id, threading.Lock())


def undo_artifact(repo, artifact, save_dir: str) -> Dict[str, Any]:
    if artifact.status != "active":
        raise DomainError("NOT_FOUND", "产物不是 active 状态", "刷新历史列表后重试", 404)
    if not os.path.isdir(artifact.dir_path):
        raise DomainError("NOT_FOUND", "产物目录不存在", "刷新历史列表或重建", 404)
    assert_inside(artifact.dir_path, save_dir)
    verification = verify_manifest(artifact.dir_path, artifact.manifest(), artifact.sha256)
    if not verification["ok"]:
        raise DomainError(
            "ARTIFACT_MODIFIED",
            "产物自创建后已被修改，不能撤销",
            "保留产物或手动移入 .trash；差异文件见 details",
            409,
            verification,
        )
    with _lock_for(artifact.id):
        target = move_to_trash(artifact.dir_path, save_dir)
        try:
            repo.mark_undone(artifact.id, target, utc_now_iso())
        except Exception as exc:
            try:
                os.replace(target, artifact.dir_path)
            except OSError:
                try:
                    shutil.move(target, artifact.dir_path)
                except OSError:
                    pass
            raise DomainError("STORAGE_ERROR", "撤销登记失败，已尝试回滚", f"检查目录占用：{exc}", 500)
    return {
        "artifact_id": artifact.id,
        "trash_path": target,
        "moved_files": len(verification.get("missing", [])) + len(artifact.manifest().get("files", [])),
        "verification": verification,
    }