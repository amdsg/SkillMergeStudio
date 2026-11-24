from __future__ import annotations

import os

import pytest

from skillmerge.services.merger.align import extract_chapters
from skillmerge.services.merger.assemble import assemble_document, prepare_chapters, trim_suggestions
from skillmerge.services.merger.conflict import decision_for, format_conflict
from skillmerge.services.merger.dependencies import aggregate, environment_section
from skillmerge.services.merger.normalize import heading_key, normalize_heading
from skillmerge.services.merger.paragraphs import dedupe_group, split_paragraphs
from skillmerge.services.parser.resources import parse_dependencies
from skillmerge.services.merger.resources_merge import merge_resources, normalize_rel
from skillmerge.services.merger.similarity import similarity
from skillmerge.util.hashing import sha256_text


def test_heading_normalization_examples():
    assert normalize_heading("## 1. 工作流程") == "工作流程"
    assert normalize_heading("- 工作流程 ") == "工作流程"
    assert normalize_heading("工作流程：") == "工作流程"
    assert normalize_heading("（1） 检查项") == "检查项"
    assert normalize_heading("Work Flow") == "work flow"
    assert normalize_heading("工作Flow") == "工作Flow"
    assert len(heading_key("长" * 300)) == 200


def test_similarity_symmetry_and_short_text():
    assert similarity("abc", "abc").value == 1.0
    assert similarity("abc", "abd").value == 0.0
    left = "一段用于比较的较长文本，包含中文和 English words。"
    right = "一段用于比较的较长文本，包含中文与 English words。"
    assert similarity(left, right).value == similarity(right, left).value


def test_decision_boundaries():
    assert decision_for(1.0) == "auto"
    assert decision_for(0.72) == "suggest"
    assert decision_for(0.35) == "review"
    assert decision_for(0.349) == "conflict"
    assert decision_for(None) == "review"
    assert decision_for(0.72, same_title=False) == "suggest"
    assert format_conflict("claude", "工作流程", 0.2) == "<!-- conflict: source=claude:工作流程, sim=0.200 -->"


def test_paragraph_fence_and_cross_source_dedupe():
    text = "第一段\n\n```bash\necho a\n\necho b\n```\n\n第二段"
    paragraphs = split_paragraphs(text)
    assert len(paragraphs) == 3
    assert "echo a\n\necho b" in paragraphs[1]["text"]

    members = [
        {"skill_id": "a", "source_index": 0, "body": "相同段落\n\n步骤一"},
        {"skill_id": "b", "source_index": 1, "body": "相同段落\n\n步骤二"},
    ]
    result = dedupe_group(members)
    assert len(result["dropped"]) == 1
    assert result["dropped"][0]["kept_from"] == "a"


def test_near_duplicate_is_not_deleted():
    base = "这是一个用于测试近似重复检测的较长段落，包含足够多的字符以确保相似度计算稳定并超过阈值。"
    changed = base.replace("较长", "很长")
    members = [
        {"skill_id": "a", "source_index": 0, "body": base},
        {"skill_id": "b", "source_index": 1, "body": changed},
    ]
    result = dedupe_group(members)
    assert result["dropped"] == []
    assert result["near_dupes"]
    assert len(result["kept"]) == 2


def test_same_source_repeats_are_kept():
    members = [{"skill_id": "a", "source_index": 0, "body": "相同段落\n\n相同段落"}]
    result = dedupe_group(members)
    assert result["dropped"] == []
    assert len(result["kept"][0]["paragraphs"]) == 2


def test_dependency_aggregation_and_section():
    packages = aggregate(
        [
            {"name": "pandas>=2.0"},
            {"name": "pandas>=2.1"},
            {"name": "PyYAML", "raw": "PyYAML==6.0"},
        ]
    )
    assert len(packages) == 2
    pandas = [item for item in packages if item["key"] == "pandas"][0]
    assert pandas["spec"] == ">=2.1"
    section = environment_section(packages)
    assert "## 环境要求" in section
    assert "python -m pip install" in section


def test_resource_merge_dedup_and_rename(tmp_path):
    first = str(tmp_path / "a")
    second = str(tmp_path / "b")
    os.makedirs(os.path.join(first, "assets"))
    os.makedirs(os.path.join(second, "assets"))
    for root in (first, second):
        with open(os.path.join(root, "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write("---\nname: x\ndescription: d\n---\n")
    with open(os.path.join(first, "assets", "same.txt"), "w", encoding="utf-8") as handle:
        handle.write("same")
    with open(os.path.join(second, "assets", "same.txt"), "w", encoding="utf-8") as handle:
        handle.write("same")
    with open(os.path.join(first, "assets", "diff.txt"), "w", encoding="utf-8") as handle:
        handle.write("one")
    with open(os.path.join(second, "assets", "diff.txt"), "w", encoding="utf-8") as handle:
        handle.write("two")
    result = merge_resources(
        [
            {"skill_id": "a", "dir": first, "source_index": 0},
            {"skill_id": "b", "dir": second, "source_index": 1},
        ]
    )
    names = {item["renamed_to"] for item in result["kept"]}
    assert "assets/same.txt" in names
    assert "assets/diff.txt" in names
    assert "assets/diff_2.txt" in names
    assert any(item.get("deduped") for item in result["decisions"])


def test_resource_path_rejects_traversal():
    with pytest.raises(ValueError):
        normalize_rel("../evil.txt")
    with pytest.raises(ValueError):
        normalize_rel("C:/Windows/evil.txt")


def test_assemble_conflict_and_frontmatter_order():
    members = [
        {"skill_id": "a", "source_index": 0, "source_label": "a", "line": 3, "title": "冲突章节",
         "norm": "冲突章节", "body": "甲方案", "body_hash": sha256_text("甲方案")},
        {"skill_id": "b", "source_index": 1, "source_label": "b", "line": 5, "title": "冲突章节",
         "norm": "冲突章节", "body": "乙方案", "body_hash": sha256_text("乙方案")},
    ]
    group = {
        "key": "冲突章节", "norm": "冲突章节", "title": "冲突章节", "level": 2,
        "members": members, "decision": "conflict", "sim": 0.2, "first_seen_rank": 1,
        "aliases_hit": False, "cross_title": False, "sim_pairs": [],
    }
    prepared = prepare_chapters([group], "keep-all", {})
    sources = [
        {"skill_id": "a", "source_hash": "h1", "path": "/a", "name": "a", "category": "未分类",
         "platform": "custom", "frontmatter": {}},
        {"skill_id": "b", "source_hash": "h2", "path": "/b", "name": "b", "category": "未分类",
         "platform": "custom", "frontmatter": {}},
    ]
    text = assemble_document("demo", "desc", sources, prepared["chapters"], [], prepared, "keep-all")
    assert "<!-- conflict: source=a:冲突章节, sim=0.200 -->" in text
    assert "甲方案" in text and "乙方案" in text
    assert sum(1 for line in text.split("\n") if line.startswith("# ")) == 1
    order = [text.index(f"{key}:") for key in ("name", "description", "version", "author", "merged-from", "generator")]
    assert order == sorted(order)
    first = assemble_document("demo", "desc", sources, prepared["chapters"], [], prepared, "keep-all")
    assert first == text


def test_dependencies_from_three_sources(tmp_path):
    root = str(tmp_path / "skill")
    os.makedirs(root)
    with open(os.path.join(root, "requirements.txt"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# comment\nnumpy>=1.20\n")
    body = "## 环境要求\n\n```bash\npip install requests\n```\n"
    deps = parse_dependencies({"Dependencies": ["pandas>=2.0"]}, body, root)
    assert {item["source"] for item in deps} == {"frontmatter", "requirements.txt", "environment-section"}
    assert {item["name"].lower() for item in deps} == {"pandas>=2.0", "numpy", "requests"}


def test_trim_suggestions_never_truncates():
    prepared = [
        {"title": "示例", "norm": "示例", "members": [{"paragraphs": ["x" * 400]}]},
        {"title": "工作流", "norm": "工作流", "members": [{"paragraphs": ["y" * 400]}]},
    ]
    before = [list(item["members"][0]["paragraphs"]) for item in prepared]
    suggestions = trim_suggestions(prepared, 900, 300)
    assert suggestions
    assert suggestions[0]["chapter"] == "示例"
    assert all("truncate" not in item for item in suggestions)
    assert [list(item["members"][0]["paragraphs"]) for item in prepared] == before


def test_extract_chapters_keeps_nested_content():
    body = "# 标题\n\n开头\n\n## 工作流程\n\n步骤一\n\n### 子步骤\n\n细节\n\n## 其他\n\n内容"
    chapters = extract_chapters(body, "s", 0, "a")
    assert [item["title"] for item in chapters] == ["标题"]
    assert "### 子步骤" in chapters[0]["body"]
    assert "细节" in chapters[0]["body"]