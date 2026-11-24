from __future__ import annotations

import hashlib
import os
import zipfile

import pytest

from skillmerge.services.exporter.export_service import ExportOptions, ExportService
from skillmerge.services.exporter.preview import export_preview
from skillmerge.services.merger.merge_service import MergeOptions
from skillmerge.storage.repos.artifacts_repo import ArtifactsRepo
from skillmerge.util.errors import DomainError
from tests.helpers import build_env, named_skills, scan, write_skill


def _setup(tmp_path):
    root = str(tmp_path / "skills")
    write_skill(root, "a", "alpha", "源 A", "## 工作流\n\n步骤一：读取数据并校验。")
    write_skill(root, "b", "beta", "源 B", "## 工作流\n\n步骤二：生成报告并保存。")
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta"])
    merged = env.merge.merge(skills, MergeOptions(name="preview-demo", platform="generic"))
    artifact = ArtifactsRepo(env.db).get(merged["artifact_id"])
    service = ExportService(env.db, env.config, env.registry)
    return env, service, artifact


def _tree_hash(root):
    digest = hashlib.sha256()
    if not os.path.isdir(root):
        return digest.hexdigest()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for filename in sorted(filenames):
            full = os.path.join(dirpath, filename)
            digest.update(os.path.relpath(full, root).replace(os.sep, "/").encode("utf-8"))
            with open(full, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


def test_preview_structure_and_zero_write(tmp_path):
    env, service, artifact = _setup(tmp_path)
    try:
        before = _tree_hash(env.config.save_dir)
        result = export_preview(
            service,
            artifact,
            ["workbuddy", "generic", "prompt-only"],
            ExportOptions(mode="zip", confirm_candidate=True),
        )
        assert result["artifact_id"] == artifact.id
        assert result["summary"] == {"total": 3, "verified": 2, "candidate": 1, "installable": 0}
        assert _tree_hash(env.config.save_dir) == before
        by_platform = {item["platform"]: item for item in result["items"]}
        workbuddy = by_platform["workbuddy"]
        assert workbuddy["planned"]["package_type"] == "zip"
        assert workbuddy["planned"]["wrap"] is True
        assert workbuddy["planned"]["skill_md_path"] == "skills/preview-demo/SKILL.md"
        assert workbuddy["requires_confirm"] is True
        assert workbuddy["install_available"] is False
        assert workbuddy["format"]["rule_status"] == "candidate"
        assert any(item["rel_path"] == "SKILL.md" for item in workbuddy["planned"]["files"])
        generic = by_platform["generic"]
        assert generic["planned"]["package_type"] == "dir"
        assert generic["planned"]["skill_md_path"] == "SKILL.md"
        assert generic["requires_confirm"] is False
        prompt = by_platform["prompt-only"]
        assert prompt["planned"]["package_type"] == "prompt"
        assert prompt["planned"]["skill_md_path"] == "prompt.md"
        assert any(item["rel_path"] == "prompt.md" for item in prompt["planned"]["files"])
        assert prompt["planned"]["total_size_bytes"] > 0
    finally:
        env.db.close_all()


def test_preview_plan_matches_real_zip(tmp_path):
    env, service, artifact = _setup(tmp_path)
    try:
        preview = export_preview(
            service,
            artifact,
            ["workbuddy"],
            ExportOptions(mode="zip", confirm_candidate=True),
        )
        planned = set(preview["items"][0]["planned"]["planned_entries"])
        real = service.export(artifact, ExportOptions(platform="workbuddy", mode="zip", confirm_candidate=True))
        with zipfile.ZipFile(real["zip_path"]) as archive:
            actual = {name for name in archive.namelist() if not name.endswith("/manifest.json")}
        assert planned == actual
    finally:
        env.db.close_all()


def test_preview_rejects_missing_artifact_and_unknown_platform(tmp_path):
    env, service, artifact = _setup(tmp_path)

    class _Missing:
        status = "active"
        dir_path = os.path.join(str(tmp_path), "missing")
        id = "missing"

    try:
        with pytest.raises(DomainError) as missing:
            service.preview_one(_Missing(), ExportOptions(platform="generic"))
        assert missing.value.code == "NOT_FOUND"
        with pytest.raises(DomainError) as unknown:
            service.preview_one(artifact, ExportOptions(platform="no-such"))
        assert unknown.value.code == "INVALID_ARGUMENT"
    finally:
        env.db.close_all()