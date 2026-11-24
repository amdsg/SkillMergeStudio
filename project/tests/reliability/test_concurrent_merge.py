from __future__ import annotations

import os
import threading

from skillmerge.services.merger.merge_service import MergeOptions
from tests.helpers import build_env, named_skills, scan, write_skill


def test_concurrent_same_name_produces_four_dirs(tmp_path):
    root = str(tmp_path / "skills")
    write_skill(root, "a", "alpha", "A", "## 工作流\n\n步骤一：读取数据并校验。")
    write_skill(root, "b", "beta", "B", "## 工作流\n\n步骤二：生成报告并保存。")
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta"])
    options = MergeOptions(name="concurrent", platform="generic")
    barrier = threading.Barrier(4)
    results = []
    errors = []

    def run():
        try:
            barrier.wait(timeout=5)
            results.append(env.merge.merge(skills, options))
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors, errors
    assert len(results) == 4
    paths = {item["dir_path"] for item in results}
    assert len(paths) == 4
    names = {os.path.basename(path) for path in paths}
    assert names == {"concurrent", "concurrent_2", "concurrent_3", "concurrent_4"}
    contents = {open(os.path.join(path, "SKILL.md"), encoding="utf-8").read() for path in paths}
    assert len(contents) == 1
    env.db.close_all()