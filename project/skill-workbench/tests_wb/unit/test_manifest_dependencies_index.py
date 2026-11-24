import json
import sys
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.core import dependencies, index_store, manifest  # noqa: E402

FRONTMATTER = """---
native_targets: [deepseek, chatgpt]
capability_tags: [summarize]
version: 1.2.0
dependencies:
  - repo: owner/dep-a
  - repo: owner/dep-b
---

# Skill
"""


def test_manifest_ok_partial_failed(tmp_path):
    ok = manifest.parse_text(FRONTMATTER)
    assert ok["parse_status"] == "ok"
    assert ok["fields"]["native_targets"] == ["deepseek", "chatgpt"]
    partial = manifest.parse_text("---\nversion: 1.0.0\n---\n")
    assert partial["parse_status"] == "partial"
    assert partial["fields"]["native_targets"] == manifest.UNKNOWN
    failed = manifest.parse_text("# no frontmatter\n")
    assert failed["parse_status"] == "failed"
    assert set(failed["unknown_fields"]) == set(manifest.FIELDS)


def test_manifest_file_and_determinism(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text(FRONTMATTER, encoding="utf-8")
    first = manifest.parse_file(path, "a" * 40)
    second = manifest.parse_file(path, "a" * 40)
    assert first["fields"] == second["fields"]
    assert first["source_commit"] == "a" * 40


def test_manifest_requires_commit(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text(FRONTMATTER, encoding="utf-8")
    try:
        manifest.parse_file(path, "")
    except Exception as error:
        assert getattr(error, "code", "") == "E_REF_INCOMPLETE"
    else:
        raise AssertionError("expected E_REF_INCOMPLETE")


def test_dependency_limits_and_denied():
    root = {
        "repo_full_name": "owner/root",
        "skill_id": "root",
        "fields": {"dependencies": [{"repo": "owner/dep-a"}, {"repo": "https://evil.example/x"}]},
    }
    plan = dependencies.build_plan(root)
    assert plan["count"] == 1
    assert plan["denied"][0]["code"] == "E_DEPENDENCY_SOURCE_DENIED"
    assert plan["items"][0]["parent_skill_id"] == "root"


def test_dependency_no_duplicates_and_limits():
    deps = [{"repo": f"owner/dep-{index}"} for index in range(25)]
    plan = dependencies.build_plan({"repo_full_name": "owner/root", "fields": {"dependencies": deps}})
    assert plan["count"] == dependencies.TOTAL_LIMIT
    assert plan["truncated"] is True
    assert len({item["repo"] for item in plan["items"]}) == plan["count"]


def test_dependency_cancel_leaves_zero_partial():
    plan = {"items": [{"repo": "owner/a"}, {"repo": "owner/b"}]}
    result = dependencies.execute(plan, lambda item: {"ok": True}, cancelled=lambda: True)
    assert result["cancelled"] is True
    assert result["completed"] == []


def test_index_rebuild_and_verify(tmp_path):
    entries = tmp_path / "imports"
    index = tmp_path / "index"
    folder = entries / "skill-a"
    folder.mkdir(parents=True)
    entry = index_store.build_entry("skill-a", "A", "owner/a", "a" * 40, {"fields": {"version": "1.0.0", "native_targets": ["unknown"], "capability_tags": ["x"]}, "parse_status": "partial"}, "imports/skill-a")
    (folder / "manifest.json").write_text(json.dumps({"index_entry": entry}), encoding="utf-8")
    index_store.write_entry(index, entry)
    assert index_store.verify(index, entries)["ok"] is True
    rebuilt = index_store.rebuild_from_disk(entries, index)
    assert len(rebuilt) == 1
    assert rebuilt[0]["skill_id"] == "skill-a"


def test_index_unique_dir(tmp_path):
    (tmp_path / "name").mkdir()
    assert index_store.unique_dir(tmp_path, "name").name == "name_2"
    (tmp_path / "name_2").mkdir()
    assert index_store.unique_dir(tmp_path, "name").name == "name_3"