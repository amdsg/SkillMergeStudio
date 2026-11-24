from __future__ import annotations

import json
import os
import zipfile

import pytest

from skillmerge.services.exporter.export_service import ExportOptions, ExportService
from skillmerge.services.exporter.manifest import resolve_download
from skillmerge.services.merger.merge_service import MergeOptions
from skillmerge.services.parser.frontmatter import read_document
from skillmerge.storage.repos.artifacts_repo import ArtifactsRepo
from skillmerge.util.errors import DomainError
from tests.helpers import build_env, named_skills, scan, write_skill


def _setup(tmp_path):
    root = str(tmp_path / "skills")
    write_skill(root, "a", "alpha", "源 A", "## 工作流\n\n步骤一：读取数据并校验。\n\n## 约束\n\n不得编造事实。", assets={"assets/logo.txt": "same"})
    write_skill(root, "b", "beta", "源 B", "## 工作流\n\n步骤二：生成报告并保存。\n\n## 示例\n\n输入示例。", assets={"assets/logo.txt": "same"})
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta"])
    merged = env.merge.merge(skills, MergeOptions(name="export-demo", platform="generic"))
    artifact = ArtifactsRepo(env.db).get(merged["artifact_id"])
    service = ExportService(env.db, env.config, env.registry)
    return env, service, artifact


def test_first_five_platforms_end_to_end(tmp_path):
    env, service, artifact = _setup(tmp_path)
    cases = [("generic", "dir"), ("claude", "zip"), ("workbuddy", "zip"), ("chatgpt", "zip"), ("prompt-only", "dir")]
    results = {}
    for platform, mode in cases:
        result = service.export(
            artifact,
            ExportOptions(
                platform=platform,
                mode=mode,
                length_mode="compact",
                profile="gpt",
                confirm_candidate=platform in ("workbuddy", "chatgpt"),
            ),
        )
        assert not [item for item in result["validation"] if item["level"] == "error"]
        assert os.path.isdir(result["dir_path"])
        results[platform] = result
        if mode == "zip":
            assert result["zip_path"] and os.path.isfile(result["zip_path"])
            with zipfile.ZipFile(result["zip_path"]) as archive:
                names = archive.namelist()
                assert names
                if platform == "claude":
                    assert f"{result['name']}/SKILL.md" in names
                if platform == "workbuddy":
                    assert f"skills/{result['name']}/SKILL.md" in names
    manifest = json.load(open(os.path.join(results["claude"]["dir_path"], "manifest.json"), encoding="utf-8"))
    assert manifest["platform"] == "claude"
    assert manifest["rule_verified_at"]
    assert manifest["files"] and manifest["dir_sha256"]
    assert manifest["total_size_bytes"] > 0
    workbuddy_doc = read_document(os.path.join(results["workbuddy"]["dir_path"], "SKILL.md"))
    for key in ("description_zh", "description_en", "version", "author"):
        assert workbuddy_doc.frontmatter.get(key)
    prompt = results["prompt-only"]
    assert prompt["kind"] == "prompt"
    assert os.path.isfile(os.path.join(prompt["dir_path"], "prompt.md"))
    manifest = open(os.path.join(prompt["dir_path"], "manifest.json"), encoding="utf-8").read()
    assert '"token_estimate"' in manifest
    assert '"estimate":true' in manifest
    env.db.close_all()


def test_claude_forbidden_name_and_download(tmp_path):
    env, service, artifact = _setup(tmp_path)
    claude = service.export(artifact, ExportOptions(platform="claude", mode="download"))
    assert claude["download_url"].endswith("/download")
    resolved = resolve_download(ArtifactsRepo(env.db).get(claude["artifact_id"]))
    assert os.path.isfile(resolved["path"])
    assert resolve_download(ArtifactsRepo(env.db).get(claude["artifact_id"]), "SKILL.md")["filename"] == "SKILL.md"
    with pytest.raises(DomainError):
        resolve_download(ArtifactsRepo(env.db).get(claude["artifact_id"]), "../SKILL.md")

    skills = named_skills(env, ["alpha", "beta"])
    bad = env.merge.merge(skills, MergeOptions(name="claude-helper", platform="generic"))
    bad_artifact = ArtifactsRepo(env.db).get(bad["artifact_id"])
    with pytest.raises(DomainError) as captured:
        service.export(bad_artifact, ExportOptions(platform="claude", mode="zip"))
    assert captured.value.code == "EXPORT_BLOCKED"
    checks = captured.value.details.get("checks", [])
    assert any(item["id"] == "V-NAME-01" for item in checks)
    env.db.close_all()