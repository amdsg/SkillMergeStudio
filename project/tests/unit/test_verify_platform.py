from __future__ import annotations

import importlib.util
import os
import platform
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def verify():
    spec = importlib.util.spec_from_file_location("verify_platform", ROOT / "tools" / "verify_platform.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def isolated():
    spec = importlib.util.spec_from_file_location(
        "check_install_isolated", ROOT / "tools" / "check_install_isolated.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_p01_platform_mapping(verify, monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(platform, "machine", lambda: "AMD64")
    assert verify.detect_platform() == ("windows", "x86_64")
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(platform, "machine", lambda: "arm64")
    assert verify.detect_platform() == ("macos", "arm64")
    monkeypatch.setattr(platform, "system", lambda: "Plan9")
    assert verify.detect_platform()[0] == "unknown"


def test_p02_guard_rejects_real_home(isolated, tmp_path):
    home = Path.home()
    assert isolated._guard(home, False) == "VERIFY_ESCAPE_REAL_HOME"
    assert isolated._guard(home, True) == ""


def test_p03_guard_rejects_tilde(isolated):
    assert isolated._guard(Path("~/skills"), True) == "VERIFY_TILDE_PATH"


def test_p04_static_checks_do_not_lift_result(verify):
    steps = [{"id": f"S{i}", "status": "pass"} for i in range(1, 6)]
    steps.append({"id": "S6", "status": "fail"})
    assert verify.aggregate_result(steps) == "fail"
    assert verify.aggregate_result([{"id": f"S{i}", "status": "pass"} for i in range(1, 7)]) == "pass"


def test_p05_snapshot_detects_content_change(isolated, tmp_path):
    root = tmp_path / "skills"
    target = root / "a.txt"
    target.parent.mkdir(parents=True)
    target.write_text("one", encoding="utf-8")
    before, _ = isolated._snapshot(root)
    target.write_text("two", encoding="utf-8")
    after, _ = isolated._snapshot(root)
    assert before["a.txt"] != after["a.txt"]


def test_p06_snapshot_ignores_mtime(isolated, tmp_path):
    root = tmp_path / "skills"
    target = root / "a.txt"
    target.parent.mkdir(parents=True)
    target.write_text("one", encoding="utf-8")
    before, _ = isolated._snapshot(root)
    os.utime(target, (1700000000, 1700000000))
    after, _ = isolated._snapshot(root)
    assert before == after


def test_p07_out_of_bounds_is_rejected(tmp_path):
    from skillmerge.services.fsops import assert_inside
    from skillmerge.util.errors import DomainError

    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(DomainError):
        assert_inside(str(root / ".." / "escape"), str(root))


def test_p08_duplicate_name_gets_suffix(tmp_path):
    from skillmerge.services.fsops import reserve_dir

    root = tmp_path / "skills"
    root.mkdir()
    first = reserve_dir(str(root), "demo")

    second = reserve_dir(str(root), "demo")
    assert Path(first).name == "demo"
    assert Path(second).name == "demo_2"


def test_p09_failed_install_goes_to_trash(tmp_path):
    from skillmerge.services.fsops import move_to_trash

    save_dir = tmp_path / "save"
    save_dir.mkdir()
    target = tmp_path / "new"
    target.mkdir()
    (target / "a.txt").write_text("x", encoding="utf-8")
    trash_path = move_to_trash(str(target), str(save_dir))
    assert not target.exists()
    assert (Path(trash_path) / "a.txt").is_file()


def test_p10_snapshot_truncates(isolated, tmp_path, monkeypatch):
    monkeypatch.setattr(isolated, "MAX_SNAPSHOT_ENTRIES", 2)
    root = tmp_path / "skills"
    root.mkdir()
    for index in range(3):
        (root / f"{index}.txt").write_text("x", encoding="utf-8")
    _result, truncated = isolated._snapshot(root)
    assert truncated is True


def test_p11_snapshot_does_not_follow_symlink(isolated, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    root = tmp_path / "skills"
    root.mkdir()
    try:
        os.symlink(outside, root / "link.txt")
    except (OSError, NotImplementedError):
        pytest.skip("Windows 不允许创建符号链接")
    result, _ = isolated._snapshot(root)
    assert result["link.txt"].startswith("link:")


def test_p12_missing_root_is_blocked(isolated, capsys):
    code = isolated.main([])
    assert code == 2
    payload = capsys.readouterr().out
    assert "missing_isolated_root" in payload