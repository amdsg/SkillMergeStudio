from __future__ import annotations

import os

from skillmerge.services.scanner import walker


def test_matches_ignore_patterns():
    assert walker._matches_ignore("a/node_modules", "node_modules", ["node_modules"])
    assert walker._matches_ignore("a/x.tmp", "x.tmp", ["*.tmp"])
    assert walker._matches_ignore("a/b", "b", ["**/b"])
    assert not walker._matches_ignore("a/b", "b", ["*.tmp"])


def test_walk_finds_skill_and_prunes(tmp_path):
    root = tmp_path / "root"
    (root / "skill").mkdir(parents=True)
    (root / "skill" / "SKILL.md").write_text("# s\n", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "SKILL.md").write_text("# x\n", encoding="utf-8")
    (root / "deep" / "a" / "b").mkdir(parents=True)
    (root / "deep" / "a" / "b" / "SKILL.md").write_text("# d\n", encoding="utf-8")

    result = walker.walk([{"path": str(root), "platform": "test"}], walker.WalkOptions(depth=2))
    dirs = {os.path.basename(os.path.dirname(item["path"])) for item in result.candidates}
    assert "skill" in dirs
    assert "node_modules" not in dirs
    assert "b" not in dirs
    assert result.accumulator.prune_hits


def test_walk_respects_limit(tmp_path):
    root = tmp_path / "root"
    for index in range(5):
        folder = root / f"s{index}"
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text("# s\n", encoding="utf-8")
    result = walker.walk([{"path": str(root), "platform": "test"}], walker.WalkOptions(limit=2))
    assert len(result.candidates) == 2
    assert result.accumulator.stats.limit_hit is True
    assert result.accumulator.uncovered_dirs


def test_walk_cancel_and_time_limit(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "SKILL.md").write_text("# s\n", encoding="utf-8")

    class _Cancel:
        def is_set(self):
            return True

    result = walker.walk([{"path": str(root), "platform": "test"}], cancel_token=_Cancel())
    assert result.cancelled is True

    result = walker.walk([{"path": str(root), "platform": "test"}], walker.WalkOptions(time_limit=0))
    assert result.accumulator.stats.time_limit_hit is True


def test_walk_roots_maps_platforms(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "SKILL.md").write_text("# s\n", encoding="utf-8")
    result = walker.walk_roots([str(root)])
    assert result.roots == [str(root)]
    assert result.candidates