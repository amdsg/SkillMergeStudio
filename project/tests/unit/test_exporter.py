from __future__ import annotations

import json
import os
import tempfile
import zipfile
from types import SimpleNamespace

import pytest

from skillmerge.services.exporter.desc import rewrite_description
from skillmerge.services.exporter.installer import install_copy
from skillmerge.services.exporter.namer import forbidden_hits, generate_name, slugify
from skillmerge.services.exporter.packer import pack, unique_zip_path
from skillmerge.services.exporter.prompt_pack import generate as generate_prompt
from skillmerge.services.exporter.registry import PlatformRegistry
from skillmerge.services.exporter.validate import run_preflight
from skillmerge.util.errors import DomainError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLATFORMS = os.path.join(ROOT, "platforms")
REGISTRY = PlatformRegistry(PLATFORMS)


def base_spec():
    text = "---\nname: demo\ndescription: desc\n---\n\n# demo\n\n正文\n"
    return {
        "name": "demo",
        "description": "desc",
        "text": text,
        "frontmatter": {"name": "demo", "description": "desc"},
        "files": [{"rel_path": "SKILL.md", "size_bytes": len(text), "kind": "document"}],
        "mode": "zip",
        "expected_prefix": "demo/",
        "layout_name": "demo",
        "planned_entries": ["demo/SKILL.md"],
    }


def test_registry_first_five_and_unknown():
    ids = {item["id"] for item in REGISTRY.public()}
    assert {"generic", "claude", "workbuddy", "chatgpt", "prompt-only"}.issubset(ids)
    workbuddy = [item for item in REGISTRY.public() if item["id"] == "workbuddy"][0]
    assert workbuddy["unknown"] is True
    assert REGISTRY.require("prompt-only")["kind"] == "prompt"


def test_registry_rejects_invalid_rule(tmp_path):
    directory = str(tmp_path / "platforms")
    os.makedirs(directory)
    with open(os.path.join(directory, "bad.json"), "w", encoding="utf-8") as handle:
        json.dump({"id": "bad"}, handle)
    with pytest.raises(DomainError):
        PlatformRegistry(directory)


def test_namer_chinese_fallback_and_forbidden():
    claude = REGISTRY.require("claude")
    name = generate_name(claude, "中文技能", category="数据分析", slug_map={"数据分析": "data-analysis"})
    assert name == "data-analysis-01"
    assert slugify("My Skill!") == "my-skill"
    assert forbidden_hits("my-claude-helper", claude) == ["claude"]
    assert forbidden_hits("my-anthropic-helper", claude) == ["anthropic"]


def test_description_rewrite_not_truncated():
    claude = REGISTRY.require("claude")
    original = "很长的描述" * 80
    text, level = rewrite_description(
        claude, original, [{"name": "a", "category": "数据分析"}, {"name": "b", "category": "数据分析"}],
        ["工作流", "约束"], "生成统计报告"
    )
    assert len(text) <= 200
    assert text.endswith("。")
    assert "合并 2 个技能" in text
    assert level in ("L1", "L2", "L3", "L4", "L5")


def test_validate_covers_fifteen_ids():
    rule = dict(REGISTRY.require("claude"))
    rule["verified_at"] = "2020-01-01"
    text = "\n".join("x" * 100 for _ in range(600))
    files = [{"rel_path": "x.exe", "size_bytes": 11 * 1024 * 1024, "kind": "binary"}]
    files.extend({"rel_path": f"f{i}.txt", "size_bytes": 160 * 1024, "kind": "document"} for i in range(201))
    spec = {
        "name": "my-claude-helper", "description": "d" * 300, "text": text,
        "frontmatter": {}, "files": files, "mode": "zip",
        "expected_prefix": "other/", "layout_name": "demo",
        "planned_entries": ["../evil.txt"],
    }
    checks = run_preflight(rule, spec)
    ids = {item["id"] for item in checks}
    expected = {
        "V-NAME-01", "V-NAME-02", "V-DESC-01", "V-MD-01", "V-MD-02", "V-MD-03",
        "V-FM-01", "V-BUNDLE-01", "V-BUNDLE-02", "V-BUNDLE-03",
        "V-ZIP-01", "V-ZIP-02", "V-RULE-01", "V-ASSET-01",
    }
    assert expected.issubset(ids)
    unknown_checks = run_preflight(REGISTRY.require("workbuddy"), base_spec())
    assert "V-RULE-02" in {item["id"] for item in unknown_checks}


def test_zip_is_deterministic_and_structured(tmp_path):
    root = str(tmp_path / "root")
    os.makedirs(os.path.join(root, "assets"))
    with open(os.path.join(root, "SKILL.md"), "w", encoding="utf-8") as handle:
        handle.write("---\nname: demo\ndescription: d\n---\n\n# demo\n")
    with open(os.path.join(root, "assets", "a.txt"), "w", encoding="utf-8") as handle:
        handle.write("a")
    first = str(tmp_path / "one.zip")
    second = str(tmp_path / "two.zip")
    pack(root, first, "demo/")
    pack(root, second, "demo/")
    assert open(first, "rb").read() == open(second, "rb").read()
    with zipfile.ZipFile(first) as archive:
        names = archive.namelist()
        assert sorted(names) == ["demo/SKILL.md", "demo/assets/a.txt"]
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
    first_name = unique_zip_path(str(tmp_path), "demo")
    open(first_name, "wb").close()
    assert unique_zip_path(str(tmp_path), "demo").endswith("demo_2.zip")


def test_install_does_not_overwrite(tmp_path):
    source = str(tmp_path / "source")
    os.makedirs(source)
    with open(os.path.join(source, "SKILL.md"), "w", encoding="utf-8") as handle:
        handle.write("---\nname: demo\ndescription: desc\n---\n\n# demo\n\n正文\n")
    rule = dict(REGISTRY.require("generic"))
    rule["install"] = {"global": str(tmp_path / "install"), "project": str(tmp_path / "install")}
    spec = base_spec()
    spec["mode"] = "install"
    first, checks = install_copy(source, rule, "global", "demo", spec, str(tmp_path), str(tmp_path / "save"))
    second, _ = install_copy(source, rule, "global", "demo", spec, str(tmp_path), str(tmp_path / "save"))
    assert os.path.basename(first) == "demo"
    assert os.path.basename(second) == "demo_2"
    assert not [item for item in checks if item["level"] == "error"]


def _prompt_artifact(tmp_path):
    directory = str(tmp_path / "artifact")
    os.makedirs(directory)
    body = (
        "# prompt-demo\n\n## 适用场景\n\n用于生成统计报告、整理数据并输出图表。\n\n"
        "## 触发条件\n\n当用户要求生成报告、分析数据或制作图表时使用。\n\n"
        "## 工作流\n\n"
        "1. 读取输入并校验字段。记录缺失项与异常值。\n"
        "2. 清洗数据并统一格式。保留原始数据来源。\n"
        "3. 生成统计指标与图表。说明每个指标的含义。\n"
        "4. 撰写结论与建议。区分事实、推断与假设。\n"
        "5. 输出报告并执行自检。附上数据来源与限制。\n\n"
        "## 工具与输入输出约定\n\n输入：CSV、Excel 或用户提供的文本。\n输出：Markdown 报告与图表说明。\n"
        "工具：可用的数据处理与绘图工具。\n\n"
        "## 约束\n\n- 不得编造事实。\n- 不得删除关键信息。\n- 不得泄露敏感数据。\n"
        "- 不确定时明确说明。\n- 不得省略数据来源。\n\n"
        "## 示例\n\n示例一：输入销售数据，输出月度趋势与异常说明。\n"
        "示例二：输入问卷数据，输出分组统计与结论。\n\n"
        "## 自检清单\n\n- 目标明确\n- 输入完整\n- 结果正确\n- 风险说明\n- 格式合规\n"
    )
    with open(os.path.join(directory, "SKILL.md"), "w", encoding="utf-8") as handle:
        handle.write("---\nname: prompt-demo\ndescription: 生成报告\n---\n\n" + body)
    return SimpleNamespace(dir_path=directory, name="prompt-demo", manifest_json="{}")


def test_prompt_pack_structure_modes_and_styles(tmp_path):
    artifact = _prompt_artifact(tmp_path)
    rule = REGISTRY.require("prompt-only")
    sources = [{"skill_id": "s1", "name": "a", "path": "/x", "category": "数据分析"}]
    full = generate_prompt(artifact, rule, "prompt-demo", "生成报告", sources, "full", "gpt")
    for title in ("角色", "适用场景", "触发条件", "工作流", "工具与输入输出约定", "约束与禁止事项", "示例", "自检清单"):
        assert f"## {title}" in full["text"]
    compact = generate_prompt(artifact, rule, "prompt-demo", "生成报告", sources, "compact", "gpt")
    minimal = generate_prompt(artifact, rule, "prompt-demo", "生成报告", sources, "minimal", "gpt")
    full_len = len(full["text"])
    assert 0.50 <= len(compact["text"]) / full_len <= 0.70
    assert 0.20 <= len(minimal["text"]) / full_len <= 0.40
    assert "<role>" in generate_prompt(artifact, rule, "prompt-demo", "生成报告", sources, "full", "claude")["text"]
    assert "【角色】" in generate_prompt(artifact, rule, "prompt-demo", "生成报告", sources, "full", "generic")["text"]
    assert full["manifest"]["token_estimate"] > 0
    assert full["manifest"]["estimate"] is True