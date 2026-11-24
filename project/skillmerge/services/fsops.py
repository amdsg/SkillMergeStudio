from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from ..util.errors import DomainError
from ..util.hashing import aggregate_hash, sha256_file

NAMING_LOCK = threading.RLock()
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
MAX_NAME = 80


def assert_inside(target: str, root: str) -> None:
    try:
        target_real = os.path.realpath(os.path.abspath(target))
        root_real = os.path.realpath(os.path.abspath(root))
        if os.path.commonpath([target_real, root_real]) != root_real:
            raise DomainError("PATH_OUT_OF_BOUNDS", f"路径越界：{target}", "选择 save_dir 内的子目录", 400)
    except ValueError:
        raise DomainError("PATH_OUT_OF_BOUNDS", f"路径不在同一卷：{target}", "选择 save_dir 内的子目录", 400)


def is_within(target: str, root: str) -> bool:
    try:
        target_real = os.path.realpath(os.path.abspath(target))
        root_real = os.path.realpath(os.path.abspath(root))
        return os.path.commonpath([target_real, root_real]) == root_real
    except ValueError:
        return False


def is_system_path(path: str) -> bool:
    real = os.path.normcase(os.path.realpath(os.path.abspath(path)))
    candidates = []
    if os.name == "nt":
        drive = os.environ.get("SystemDrive", "C:")
        candidates = [
            os.path.join(drive, os.sep, "Windows"),
            os.path.join(drive, os.sep, "Program Files"),
            os.path.join(drive, os.sep, "Program Files (x86)"),
            os.path.join(drive, os.sep, "ProgramData"),
        ]
    else:
        candidates = ["/etc", "/usr", "/bin", "/sbin", "/System", "/Library"]
    for candidate in candidates:
        root = os.path.normcase(os.path.realpath(candidate))
        if real == root or real.startswith(root + os.sep):
            return True
    return False


def safe_component(name: str) -> str:
    value = _INVALID.sub("-", str(name or "")).strip(" .")
    value = re.sub(r"\s+", " ", value)
    return value[:MAX_NAME] or "skill"


def reserve_dir(parent: str, name: str) -> str:
    os.makedirs(parent, exist_ok=True)
    base = safe_component(name)
    with NAMING_LOCK:
        for index in range(1, 1000):
            candidate = os.path.join(parent, base if index == 1 else f"{base}_{index}")
            try:
                os.makedirs(candidate)
                return candidate
            except FileExistsError:
                continue
    raise DomainError("NAME_EXHAUSTED", "同名目录已存在 999 个", "更换产物名称后重试", 409)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")


def _retry_call(func, attempts: int = 12, delay: float = 0.05):
    last_error = None
    for index in range(attempts):
        try:
            return func()
        except PermissionError as exc:
            last_error = exc
            time.sleep(min(0.5, delay * (index + 1)))
    raise last_error  # type: ignore[misc]


def move_to_trash(path: str, save_dir: str) -> str:
    if not os.path.exists(path):
        return ""
    trash_root = os.path.join(save_dir, ".trash")
    os.makedirs(trash_root, exist_ok=True)
    target = os.path.join(trash_root, f"{_stamp()}-{uuid.uuid4().hex[:8]}")
    try:
        _retry_call(lambda: os.replace(path, target), attempts=5)
    except OSError:
        try:
            shutil.move(path, target)
        except OSError as exc:
            raise DomainError("TRASH_MOVE_FAILED", "无法移动到 .trash", f"手动检查并保留 {path}：{exc}", 500)
    return target


class Staging:
    def __init__(self, save_dir: str, token: Optional[str] = None) -> None:
        self.save_dir = os.path.abspath(save_dir)
        self.token = token or uuid.uuid4().hex
        self.root = os.path.join(self.save_dir, ".staging", self.token)
        os.makedirs(self.root, exist_ok=True)
        assert_inside(self.root, self.save_dir)

    def _target(self, rel_path: str) -> str:
        relative = str(rel_path).replace("\\", "/")
        if relative.startswith("/") or ".." in relative.split("/"):
            raise DomainError("PATH_OUT_OF_BOUNDS", f"staging 相对路径非法：{rel_path}", "使用安全的相对路径", 400)
        target = os.path.join(self.root, relative.replace("/", os.sep))
        assert_inside(target, self.root)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        return target

    def write_text(self, rel_path: str, text: str, fsync: bool = True) -> str:
        target = self._target(rel_path)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            if fsync:
                handle.flush()
                os.fsync(handle.fileno())
        return target

    def write_json(self, rel_path: str, payload: Dict[str, Any]) -> str:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        return self.write_text(rel_path, text)

    def copy_file(self, source: str, rel_path: str) -> str:
        if os.path.islink(source):
            raise DomainError("SYMLINK_REJECTED", "不复制符号链接", "移除符号链接后重试", 400)
        target = self._target(rel_path)
        shutil.copyfile(source, target)
        if not os.path.isfile(target):
            raise DomainError("STAGING_WRITE_FAILED", f"资源复制失败：{rel_path}", "检查源文件权限", 500)
        return target

    def commit(self, reserved_path: str) -> str:
        assert_inside(reserved_path, self.save_dir)
        with NAMING_LOCK:
            if os.path.isdir(reserved_path):
                try:
                    _retry_call(lambda: os.rmdir(reserved_path), attempts=8)
                except PermissionError as exc:
                    raise DomainError("COMMIT_FAILED", "保留目录被占用，无法提交", f"检查 {reserved_path}：{exc}", 500)
                except OSError as exc:
                    raise DomainError("COMMIT_FAILED", "保留目录非空，无法提交", f"检查 {reserved_path}：{exc}", 500)
            try:
                _retry_call(lambda: os.replace(self.root, reserved_path))
            except PermissionError as exc:
                raise DomainError("COMMIT_FAILED", "产物目录被占用，无法提交", f"稍后重试或关闭占用程序：{exc}", 500)
        self.root = ""
        return reserved_path

    def trash(self) -> str:
        if not self.root or not os.path.isdir(self.root):
            return ""
        target = move_to_trash(self.root, self.save_dir)
        self.root = ""
        return target


def file_entries(root: str) -> List[Dict[str, Any]]:
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in (".git", "__pycache__"))
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            entries.append(
                {"path": rel, "size_bytes": os.path.getsize(full), "sha256": sha256_file(full)}
            )
    entries.sort(key=lambda item: item["path"])
    return entries


def directory_hash(root: str, exclude: Iterable[str] = ()) -> str:
    skipped = {str(item).replace("\\", "/") for item in exclude}
    entries = [(item["path"], item["sha256"]) for item in file_entries(root) if item["path"] not in skipped]
    return aggregate_hash(entries)