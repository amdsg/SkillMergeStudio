"""Safe archive extraction and fixture tree copy."""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from agent.http.errors import DomainError

MAX_FILES = 5000
MAX_TOTAL_BYTES = 200 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024
IGNORED_SUFFIXES = {".sh", ".bat", ".ps1", ".exe", ".dll", ".so", ".dylib"}


def _ignore_reason(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in IGNORED_SUFFIXES:
        return "script" if suffix in {".sh", ".bat", ".ps1"} else "binary"
    return ""


def _guard_destination(dest: Path, name: str) -> Path:
    target = (dest / name).resolve()
    if not target.is_relative_to(dest.resolve()):
        raise DomainError("E_LINK_ESCAPE", "wb.error.path_denied",
                          params={"name": name}, fix_key="wb.fix.check_input")
    return target


def extract_zip(archive: Path, dest: Path) -> tuple[list[str], list[dict]]:
    dest.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    ignored: list[dict] = []
    total = 0
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) > MAX_FILES:
            raise DomainError("E_ARCHIVE_TOO_LARGE", "wb.error.archive_too_large",
                              params={"files": len(members)}, fix_key="wb.fix.split_source")
        for member in members:
            if member.is_dir():
                continue
            reason = _ignore_reason(member.filename)
            if reason:
                ignored.append({"name": member.filename, "reason": reason})
                continue
            if member.file_size > MAX_FILE_BYTES:
                raise DomainError("E_ARCHIVE_TOO_LARGE", "wb.error.archive_too_large",
                                  params={"file": member.filename}, fix_key="wb.fix.split_source")
            total += member.file_size
            if total > MAX_TOTAL_BYTES:
                raise DomainError("E_ARCHIVE_TOO_LARGE", "wb.error.archive_too_large",
                                  params={"total": total}, fix_key="wb.fix.split_source")
            target = _guard_destination(dest, member.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            files.append(member.filename)
    return files, ignored


def copy_tree(source: Path, dest: Path) -> tuple[list[str], list[dict]]:
    dest.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    ignored: list[dict] = []
    count = 0
    total = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        count += 1
        if count > MAX_FILES:
            raise DomainError("E_ARCHIVE_TOO_LARGE", "wb.error.archive_too_large",
                              params={"files": count}, fix_key="wb.fix.split_source")
        relative = path.relative_to(source).as_posix()
        reason = _ignore_reason(relative)
        if reason:
            ignored.append({"name": relative, "reason": reason})
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise DomainError("E_ARCHIVE_TOO_LARGE", "wb.error.archive_too_large",
                              params={"file": relative}, fix_key="wb.fix.split_source")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise DomainError("E_ARCHIVE_TOO_LARGE", "wb.error.archive_too_large",
                              params={"total": total}, fix_key="wb.fix.split_source")
        target = _guard_destination(dest, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        files.append(relative)
    return files, ignored