from __future__ import annotations

import os
import re
import unicodedata
import zipfile
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Optional

from ...util.errors import DomainError

FIXED_TIME = (1980, 1, 1, 0, 0, 0)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _entry_name(prefix: str, rel_path: str) -> str:
    rel = str(rel_path).replace("\\", "/")
    if not rel or rel.startswith("/") or re.match(r"^[A-Za-z]:", rel):
        raise DomainError("EXPORT_BLOCKED", f"zip 条目路径非法：{rel}", "使用相对路径", 466)
    path = PurePosixPath(rel)
    if any(part in ("", ".", "..") for part in path.parts) or _CONTROL.search(rel):
        raise DomainError("EXPORT_BLOCKED", f"zip 条目路径非法：{rel}", "规范化资源路径", 466)
    name = prefix + str(path)
    return unicodedata.normalize("NFC", name)


def _files(root: str, exclude: Iterable[str]) -> List[str]:
    blocked = {str(item).replace("\\", "/") for item in exclude}
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel in blocked or name.lower().endswith(".zip"):
                continue
            result.append(rel)
    return sorted(result, key=lambda item: item.encode("utf-8"))


def pack(root: str, zip_path: str, prefix: str = "", exclude: Iterable[str] = ("manifest.json",)) -> str:
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    prefix = prefix or ""
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for rel in _files(root, exclude):
            info = zipfile.ZipInfo(_entry_name(prefix, rel), date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            info.create_system = 3
            with open(os.path.join(root, rel), "rb") as handle:
                archive.writestr(info, handle.read())
    verify(zip_path, prefix)
    return zip_path


def verify(zip_path: str, prefix: str = "") -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            if info.date_time != FIXED_TIME:
                raise DomainError("EXPORT_BLOCKED", "zip 时间戳不可复现", "重新打包", 466)
            if info.filename.startswith("/") or ".." in info.filename.split("/"):
                raise DomainError("EXPORT_BLOCKED", f"zip 条目非法：{info.filename}", "重新打包", 466)
            if prefix and not info.filename.startswith(prefix):
                raise DomainError("EXPORT_BLOCKED", f"zip 顶层结构不符合 {prefix}", "检查 package.skill_md_path", 466)


def unique_zip_path(parent: str, base_name: str) -> str:
    os.makedirs(parent, exist_ok=True)
    candidate = os.path.join(parent, f"{base_name}.zip")
    index = 2
    while os.path.exists(candidate):
        candidate = os.path.join(parent, f"{base_name}_{index}.zip")
        index += 1
    return candidate