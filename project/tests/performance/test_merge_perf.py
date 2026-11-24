from __future__ import annotations

import os
import time

from skillmerge.services.merger.merge_service import MergeOptions
from tests.helpers import build_env, named_skills, scan, write_skill


def test_merge_ten_medium_skills_under_ten_seconds(tmp_path):
    root = str(tmp_path / "skills")
    names = []
    for index in range(10):
        name = f"medium-{index}"
        names.append(name)
        paragraphs = "\n\n".join(
            f"步骤{step}：这是第 {index} 个技能的第 {step} 个操作说明，包含输入校验与输出约定。"
            for step in range(1, 7)
        )
        write_skill(root, f"skill-{index}", name, f"中等技能 {index}", f"## 工作流\n\n{paragraphs}")
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, names)
    assert all(skills)
    started = time.monotonic()
    result = env.merge.merge(skills, MergeOptions(name="medium-merged", platform="generic"))
    elapsed = time.monotonic() - started
    assert result["sources_count"] == 10
    text = open(os.path.join(result["dir_path"], "SKILL.md"), encoding="utf-8").read()
    for index in range(10):
        assert f"第 {index} 个技能的第 1 个操作说明" in text
    assert elapsed < 10.0, f"合并耗时 {elapsed:.3f}s"
    env.db.close_all()