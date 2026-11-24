from __future__ import annotations

import json
import os

from skillmerge.services.merger.merge_service import MergeOptions
from tests.helpers import build_env, named_skills, scan, write_skill

LONG_ONE = "共同段落内容比较长，用于确认跨源完全相同段落会被去重。"
LONG_STEP = "步骤一：读取输入数据并校验字段，记录异常。"
EXTRA_STEP = "步骤二：生成统计报告并保存结果，附上数据来源。"
INSTALL = "安装说明：将技能目录复制到目标位置，并确认 SKILL.md 可正常读取。"


def _fixture(tmp_path):
    root = str(tmp_path / "skills")
    write_skill(
        root, "a", "alpha", "源 A",
        f"## 工作流程\n\n{LONG_ONE}\n\n{LONG_STEP}\n\n## 安装\n\n{INSTALL}\n\n## 冲突章节\n\n甲方案",
        assets={"assets/logo.txt": "same"},
        extra={"Dependencies": ["pandas>=2.0"]},
    )
    write_skill(
        root, "b", "beta", "源 B",
        f"## 工作流程\n\n{LONG_ONE}\n\n{LONG_STEP}\n\n{EXTRA_STEP}\n\n## 安装\n\n{INSTALL}",
        assets={"assets/logo.txt": "same"},
    )
    write_skill(
        root, "c", "gamma", "源 C",
        "## 冲突章节\n\n乙方案",
        assets={"assets/logo.txt": "different"},
    )
    return root


def test_merge_preserves_conflicts_resources_and_is_deterministic(tmp_path):
    root = _fixture(tmp_path)
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta", "gamma"])
    assert all(skills)
    options = MergeOptions(name="merged-demo", platform="generic", strategy="keep-all")
    save_dir = env.config.save_dir
    assert not os.path.isdir(save_dir)
    mtimes = [os.path.getmtime(os.path.join(os.path.dirname(skill.path), "SKILL.md")) for skill in skills]
    preview = env.merge.preview(skills, options)
    assert preview["chapters"]
    assert preview["dedup"]["duplicate_paragraphs"] >= 1
    assert not os.path.isdir(save_dir)
    assert mtimes == [os.path.getmtime(os.path.join(os.path.dirname(skill.path), "SKILL.md")) for skill in skills]

    first = env.merge.merge(skills, options, job_id="t1")
    text = open(os.path.join(first["dir_path"], "SKILL.md"), encoding="utf-8").read()
    assert text.count(LONG_ONE) == 1
    assert EXTRA_STEP in text
    assert "甲方案" in text and "乙方案" in text
    assert "<!-- conflict:" in text
    assert "## 环境要求" in text
    assert "python -m pip install" in text
    assert sum(1 for line in text.split("\n") if line.startswith("# ")) == 1
    assert set(os.listdir(os.path.join(first["dir_path"], "assets"))) == {"logo.txt", "logo_2.txt"}
    plan = open(os.path.join(first["dir_path"], "merge_plan.json"), encoding="utf-8").read()
    assert '"strategy":"keep-all"' in plan
    assert "created_at" not in plan

    second = env.merge.merge(skills, options, job_id="t2")
    assert first["dir_path"] != second["dir_path"]
    second_text = open(os.path.join(second["dir_path"], "SKILL.md"), encoding="utf-8").read()
    second_plan = open(os.path.join(second["dir_path"], "merge_plan.json"), encoding="utf-8").read()
    assert text == second_text
    assert plan == second_plan
    assert first["sha256"] == second["sha256"]
    env.db.close_all()


def test_all_strategies_write_plan_strategy(tmp_path):
    root = _fixture(tmp_path)
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta", "gamma"])
    for strategy in ("keep-all", "prefer-first", "prefer-largest", "manual"):
        options = MergeOptions(
            name=f"strategy-{strategy}", platform="generic", strategy=strategy
        )
        preview = env.merge.preview(skills, options)
        options.decisions = {
            item["key"]: "keepBoth"
            for item in preview["chapters"]
            if item["decision"] in ("suggest", "conflict")
        }
        result = env.merge.merge(skills, options)
        plan = json.load(open(os.path.join(result["dir_path"], "merge_plan.json"), encoding="utf-8"))
        assert plan["strategy"] == strategy
        if strategy in ("prefer-first", "prefer-largest"):
            assert plan["omitted"]
    env.db.close_all()


def test_prefer_first_records_omitted_content(tmp_path):
    root = _fixture(tmp_path)
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta"])
    options = MergeOptions(name="prefer-first-demo", platform="generic", strategy="prefer-first")
    preview = env.merge.preview(skills, options)
    assert preview["plan_summary"]["strategy"] == "prefer-first"
    result = env.merge.merge(skills, options)
    plan = open(os.path.join(result["dir_path"], "merge_plan.json"), encoding="utf-8").read()
    assert '"strategy":"prefer-first"' in plan
    text = open(os.path.join(result["dir_path"], "SKILL.md"), encoding="utf-8").read()
    assert "已省略内容" in text
    env.db.close_all()