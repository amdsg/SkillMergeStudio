from __future__ import annotations

import json
import os

from skillmerge.services.exporter.export_service import ExportOptions, ExportService
from skillmerge.services.merger.merge_service import MergeOptions
from skillmerge.storage.repos.artifacts_repo import ArtifactsRepo
from tests.helpers import build_env, named_skills, scan, write_skill


def _setup(tmp_path):
    root = str(tmp_path / "skills")
    write_skill(root, "a", "alpha", "源 A", "## 工作流\n\n步骤一：读取数据并校验。")
    write_skill(root, "b", "beta", "源 B", "## 工作流\n\n步骤二：生成报告并保存。")
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta"])
    merged = env.merge.merge(skills, MergeOptions(name="trace-demo", platform="generic"))
    artifact = ArtifactsRepo(env.db).get(merged["artifact_id"])
    service = ExportService(env.db, env.config, env.registry)
    return env, service, artifact


def _manifest(result):
    path = os.path.join(result["dir_path"], "manifest.json")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def test_manifest_trace_for_verified_zip(tmp_path):
    env, service, artifact = _setup(tmp_path)
    try:
        result = service.export(artifact, ExportOptions(platform="claude", mode="zip"))
        manifest = _manifest(result)
        assert manifest["platform"] == "claude"
        assert manifest["rule_source"]
        assert manifest["rule_verified_at"]
        assert manifest["package_type"] == "zip"
        assert manifest["format"] == {
            "wrap": False,
            "skill_md_path": "<name>/SKILL.md",
            "rule_status": "verified",
            "limits_source": "verified",
            "install_available": True,
        }
        for key in ("files", "total_size_bytes", "dir_sha256", "sources", "plan_summary", "created_at", "tool_version"):
            assert key in manifest
        assert isinstance(manifest["files"], list)
        assert manifest["files"]
        assert not any(item["rel_path"] == "manifest.json" for item in manifest["files"])
        assert manifest["total_size_bytes"] == sum(item["size_bytes"] for item in manifest["files"])
    finally:
        env.db.close_all()


def test_manifest_trace_for_candidate_dir(tmp_path):
    env, service, artifact = _setup(tmp_path)
    try:
        result = service.export(artifact, ExportOptions(platform="codex", mode="dir", confirm_candidate=True))
        manifest = _manifest(result)
        assert manifest["platform"] == "codex"
        assert manifest["package_type"] == "dir"
        assert manifest["format"]["wrap"] is False
        assert manifest["format"]["skill_md_path"] == "SKILL.md"
        assert manifest["format"]["rule_status"] == "candidate"
        assert manifest["format"]["limits_source"] == "legacy_limits"
        assert manifest["format"]["install_available"] is False
        assert manifest["rule_verified_at"] == "unknown"
        assert manifest["dir_sha256"]
    finally:
        env.db.close_all()


def test_manifest_trace_for_prompt(tmp_path):
    env, service, artifact = _setup(tmp_path)
    try:
        result = service.export(artifact, ExportOptions(platform="prompt-only", mode="dir"))
        manifest = _manifest(result)
        assert manifest["package_type"] == "prompt"
        assert manifest["format"]["skill_md_path"] == "prompt.md"
        assert manifest["format"]["install_available"] is False
        assert manifest["kind"] == "prompt"
        assert manifest["format"]["rule_status"] == "verified"
    finally:
        env.db.close_all()