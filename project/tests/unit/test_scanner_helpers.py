from __future__ import annotations

from skillmerge.services.scanner import discover, drives


def test_candidate_roots_include_home_appdata_local_and_project():
    items = discover._candidate_roots("/home/u", "/appdata", "/local", "/project")
    assert items
    platforms = {platform for _path, platform in items}
    assert "project" in platforms
    assert len(items) > len(platforms)


def test_detect_roots_filters_missing_and_dedupes_extra(tmp_path):
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    extra = tmp_path / "extra"
    extra.mkdir()
    roots = discover.detect_roots(
        home=str(home),
        env={"APPDATA": "", "LOCALAPPDATA": ""},
        extra_roots=[str(extra), str(extra)],
    )
    paths = [item["path"] for item in roots]
    assert str(home / ".claude" / "skills") in paths
    assert str(extra) in paths
    assert paths.count(str(extra)) == 1
    assert all(item["exists"] for item in roots)


def test_detect_roots_include_missing(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    roots = discover.detect_roots(home=str(home), env={}, include_missing=True)
    assert roots
    assert any(not item["exists"] for item in roots)


def test_platform_for_path_uses_longest_match():
    roots = [
        {"path": "C:/alpha", "platform": "one"},
        {"path": "C:/alpha/beta", "platform": "two"},
    ]
    assert discover.platform_for_path("C:/alpha/beta/gamma/SKILL.md", roots) == "two"
    assert discover.platform_for_path("C:/alpha/other", roots) == "one"
    assert discover.platform_for_path("D:/elsewhere", roots) == "unknown"


def test_existing_root_paths_only_returns_existing():
    roots = [{"path": "a", "exists": True}, {"path": "b", "exists": False}]
    assert discover.existing_root_paths(roots) == ["a"]


def test_select_drives_filters_types(monkeypatch):
    mapping = [
        {"path": "C:\\", "type": "fixed"},
        {"path": "D:\\", "type": "removable"},
        {"path": "E:\\", "type": "network"},
        {"path": "F:\\", "type": "cdrom"},
        {"path": "G:\\", "type": "ramdisk"},
    ]
    monkeypatch.setattr(drives, "enumerate_drives", lambda: mapping)
    assert drives.select_drives() == [{"path": "C:\\", "type": "fixed"}]
    assert [item["path"] for item in drives.select_drives(True, True)] == ["C:\\", "D:\\", "E:\\"]


def test_enumerate_and_posix_fallback_are_shaped():
    values = drives.enumerate_drives()
    assert isinstance(values, list)
    for item in values:
        assert item["path"]
        assert item["type"]
    posix = drives._posix_drives()
    assert posix[0]["type"] == "fixed"