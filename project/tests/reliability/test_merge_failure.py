from __future__ import annotations

import os

import pytest

from skillmerge.services import fsops
from skillmerge.services.merger.merge_service import MergeOptions
from tests.helpers import build_env, named_skills, scan, write_skill


def test_staging_failure_leaves_no_target_and_trash_copy(tmp_path, monkeypatch):
    root = str(tmp_path / "skills")
    write_skill(
        root,
        "a",
        "atomic",
        "原子写入测试",
        "## 工作流\n\n步骤一：写入资源。",
        assets={"assets/a.txt": "a", "assets/b.txt": "b", "assets/c.txt": "c"},
    )
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["atomic"])
    original = fsops.Staging.copy_file
    calls = {"count": 0}

    def flaky(self, source, rel_path):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated write failure")
        return original(self, source, rel_path)

    monkeypatch.setattr(fsops.Staging, "copy_file", flaky)
    with pytest.raises(OSError):
        env.merge.merge(skills, MergeOptions(name="atomic-artifact", platform="generic"))
    save_dir = env.config.save_dir
    assert not os.path.isdir(os.path.join(save_dir, "atomic-artifact"))
    trash = os.path.join(save_dir, ".trash")
    assert os.path.isdir(trash)
    entries = os.listdir(trash)
    assert entries
    leftover = os.path.join(trash, entries[0])
    assert os.path.isfile(os.path.join(leftover, "SKILL.md"))
    env.db.close_all()