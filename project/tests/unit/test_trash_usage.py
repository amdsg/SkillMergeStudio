from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture()
def usage():
    spec = importlib.util.spec_from_file_location(
        "trash_usage", ROOT / "skillmerge" / "services" / "history" / "trash_usage.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def gate():
    spec = importlib.util.spec_from_file_location("check_no_auto_delete", ROOT / "tools" / "check_no_auto_delete.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _file(path: Path, size: int = 8, mtime: float = 0.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


def test_r01_missing_trash_returns_zero_without_creating(usage, tmp_path):
    result = usage.trash_usage(str(tmp_path), now=NOW)
    assert result["count"] == 0 and result["bytes"] == 0
    assert not (tmp_path / ".trash").exists()


def test_r02_counts_file_and_directory(usage, tmp_path):
    _file(tmp_path / ".trash" / "entry1" / "a.txt", 10)
    _file(tmp_path / ".trash" / "entry2", 5)
    result = usage.trash_usage(str(tmp_path), now=NOW)
    assert result["count"] == 2
    assert result["bytes"] == 15


def test_r03_is_readonly(usage, tmp_path):
    target = _file(tmp_path / ".trash" / "entry" / "a.txt", 10)
    before = (hashlib.sha256(target.read_bytes()).hexdigest(), target.stat().st_mtime)
    usage.trash_usage(str(tmp_path), now=NOW)
    after = (hashlib.sha256(target.read_bytes()).hexdigest(), target.stat().st_mtime)
    assert before == after


def test_r04_over_retention_only_flags(usage, tmp_path):
    old = (NOW - timedelta(days=40)).timestamp()
    target = _file(tmp_path / ".trash" / "old-entry", 10, mtime=old)
    result = usage.trash_usage(str(tmp_path), retain_days=30, now=NOW)
    assert result["over_retention"] is True
    assert target.exists()


def test_r05_over_capacity_only_flags(usage, tmp_path):
    target = _file(tmp_path / ".trash" / "big-entry", 1024 * 1024, mtime=NOW.timestamp())
    result = usage.trash_usage(str(tmp_path), max_gb=0.000001, now=NOW)
    assert result["over_capacity"] is True
    assert target.exists()


def test_r06_symlink_not_followed(usage, tmp_path):
    outside = _file(tmp_path / "outside" / "big.bin", 4096, mtime=NOW.timestamp())
    link = tmp_path / ".trash" / "link"
    (tmp_path / ".trash").mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        pytest.skip("Windows 不允许创建符号链接")
    result = usage.trash_usage(str(tmp_path), now=NOW)
    assert result["bytes"] == 0
    assert result["unreadable"] >= 1


def test_r07_truncated_at_max_items(usage, tmp_path, monkeypatch):
    monkeypatch.setattr(usage, "MAX_ITEMS", 2)
    for index in range(3):
        _file(tmp_path / ".trash" / f"e{index}" / "a.txt", 1, mtime=NOW.timestamp())
    result = usage.trash_usage(str(tmp_path), now=NOW)
    assert result["truncated"] is True
    assert len(result["items"]) <= 2


def test_r08_permission_error_is_counted(usage, tmp_path, monkeypatch):
    _file(tmp_path / ".trash" / "entry" / "a.txt", 1, mtime=NOW.timestamp())
    original = os.lstat

    def guarded(path):
        if str(path).endswith(os.sep + "entry"):
            raise PermissionError("denied")
        return original(path)

    monkeypatch.setattr(usage.os, "lstat", guarded)
    result = usage.trash_usage(str(tmp_path), now=NOW)
    assert result["unreadable"] >= 1


def test_g01_gate_detects_rmtree_on_trash(gate, tmp_path):
    target = tmp_path / "skillmerge" / "bad.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "import shutil, os\n\ndef clean(save_dir):\n    shutil.rmtree(os.path.join(save_dir, '.trash'))\n",
        encoding="utf-8",
    )
    assert gate.main(["--root", str(tmp_path)]) == 1


def test_g02_real_repository_is_clean(gate):
    assert gate.main([]) == 0


def test_g03_gate_detects_auto_config(gate, tmp_path):
    target = tmp_path / "config" / "bad.py"
    target.parent.mkdir(parents=True)
    target.write_text("AUTO = {'trash.auto_cleanup': True}\n", encoding="utf-8")
    assert gate.main(["--root", str(tmp_path)]) == 1