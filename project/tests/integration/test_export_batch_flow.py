from __future__ import annotations

import hashlib
import os
import zipfile

import pytest

from skillmerge.api.schemas import export_params
from skillmerge.services.exporter.batch import ExportBatch, preflight_batch
from skillmerge.services.exporter.export_service import ExportOptions, ExportService
from skillmerge.services.merger.merge_service import MergeOptions
from skillmerge.storage.repos.artifacts_repo import ArtifactsRepo
from skillmerge.util.errors import DomainError
from tests.helpers import build_env, named_skills, scan, write_skill


def _setup(tmp_path, name="batch-demo"):
    root = str(tmp_path / "skills")
    write_skill(root, "a", "alpha", "源 A", "## 工作流\n\n步骤一：读取数据并校验。\n\n## 约束\n\n不得编造事实。")
    write_skill(root, "b", "beta", "源 B", "## 工作流\n\n步骤二：生成报告并保存。\n\n## 示例\n\n输入示例。")
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta"])
    merged = env.merge.merge(skills, MergeOptions(name=name, platform="generic"))
    artifact = ArtifactsRepo(env.db).get(merged["artifact_id"])
    service = ExportService(env.db, env.config, env.registry)
    return env, service, artifact


def _digest_tree(root):
    digest = hashlib.sha256()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for filename in sorted(filenames):
            full = os.path.join(dirpath, filename)
            digest.update(os.path.relpath(full, root).replace(os.sep, "/").encode("utf-8"))
            with open(full, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


def test_export_params_batch_validation():
    params = export_params(
        {"artifact_id": "a", "platforms": ["claude", "claude", "generic", " "], "mode": "dir"}
    )
    assert params["platforms"] == ["claude", "generic"]
    assert params["platform"] == "claude"
    assert export_params({"artifact_id": "a", "platform": "claude"})["platforms"] == []
    assert export_params({"artifact_id": "a"})["platform"] == "generic"

    with pytest.raises(DomainError) as empty:
        export_params({"artifact_id": "a", "platforms": []})
    assert empty.value.code == "EXPORT_BATCH_EMPTY"
    with pytest.raises(DomainError) as large:
        export_params({"artifact_id": "a", "platforms": ["p%d" % i for i in range(29)]})
    assert large.value.code == "EXPORT_BATCH_TOO_LARGE"
    assert large.value.details == {"max": 28, "requested": 29}
    with pytest.raises(DomainError) as invalid:
        export_params({"artifact_id": "a", "platforms": "claude"})
    assert invalid.value.code == "INVALID_ARGUMENT"
    with pytest.raises(DomainError):
        export_params({"artifact_id": "a", "platforms": [1, 2]})


def test_preflight_candidate_unknown_install(tmp_path):
    env, _, _ = _setup(tmp_path)
    try:
        with pytest.raises(DomainError) as candidate:
            preflight_batch(env.registry, ["workbuddy"], "dir", False)
        assert candidate.value.code == "PLATFORM_NOT_SELECTABLE"
        assert candidate.value.details["candidates"] == ["workbuddy"]
        preflight_batch(env.registry, ["workbuddy"], "dir", True)

        with pytest.raises(DomainError) as install:
            preflight_batch(env.registry, ["codex"], "install", True)
        assert install.value.code == "EXPORT_INSTALL_UNAVAILABLE"
        assert install.value.status == 466
        assert install.value.details["platforms"] == ["codex"]

        with pytest.raises(DomainError) as unknown:
            preflight_batch(env.registry, ["no-such-platform"], "dir", False)
        assert unknown.value.code == "EXPORT_PLATFORM_UNKNOWN"
        assert unknown.value.details["platforms"] == ["no-such-platform"]
    finally:
        env.db.close_all()


def test_batch_four_platforms_structure(tmp_path):
    env, service, artifact = _setup(tmp_path)
    progress = []
    try:
        result = ExportBatch(service, env.registry).run(
            artifact,
            ["claude", "workbuddy", "codex", "prompt-only"],
            ExportOptions(mode="zip", confirm_candidate=True),
            progress=lambda phase, current, total, message: progress.append((phase, current, total, message)),
        )
        assert result["batch"] is True
        assert result["source_artifact_id"] == artifact.id
        assert len(result["items"]) == 4
        assert result["summary"] == {"total": 4, "succeeded": 4, "failed": 0, "cancelled": 0}
        assert "cancelled" not in result
        by_platform = {item["platform"]: item for item in result["items"]}
        assert by_platform["claude"]["format"]["package_type"] == "zip"
        assert by_platform["workbuddy"]["format"]["wrap"] is True
        assert by_platform["codex"]["format"]["package_type"] == "dir"
        assert by_platform["prompt-only"]["format"]["package_type"] == "prompt"
        assert by_platform["workbuddy"]["format"]["rule_status"] == "candidate"
        assert by_platform["claude"]["format"]["rule_status"] == "verified"
        for item in result["items"]:
            assert item["status"] == "succeeded"
            assert item["zip_path"] and os.path.isfile(item["zip_path"])
            assert item["sha256"] and item["size_bytes"] > 0
            assert item["error"] is None
        with zipfile.ZipFile(by_platform["claude"]["zip_path"]) as archive:

            assert any(name.endswith("/SKILL.md") for name in archive.namelist())
            assert not any(name == "SKILL.md" for name in archive.namelist())
        with zipfile.ZipFile(by_platform["workbuddy"]["zip_path"]) as archive:
            assert any(name.startswith("skills/") and name.endswith("/SKILL.md") for name in archive.namelist())
        with zipfile.ZipFile(by_platform["codex"]["zip_path"]) as archive:
            assert "SKILL.md" in archive.namelist()
        with zipfile.ZipFile(by_platform["prompt-only"]["zip_path"]) as archive:
            assert "prompt.md" in archive.namelist()
        assert progress[0][0] == "export"
        assert progress[0][1:3] == (1, 4)
        assert progress[-1][1:3] == (4, 4)
        assert all("·" in item[3] for item in progress if item[0] == "export")
    finally:
        env.db.close_all()


def test_batch_partial_failure_keeps_success(tmp_path):
    env, service, artifact = _setup(tmp_path, name="claude-helper")
    before = _digest_tree(artifact.dir_path)
    try:
        result = ExportBatch(service, env.registry).run(
            artifact,
            ["claude", "generic"],
            ExportOptions(mode="dir", confirm_candidate=True),
        )
        assert result["summary"] == {"total": 2, "succeeded": 1, "failed": 1, "cancelled": 0}
        by_platform = {item["platform"]: item for item in result["items"]}
        assert by_platform["claude"]["status"] == "failed"
        assert by_platform["claude"]["error"]["code"] == "EXPORT_BLOCKED"
        assert any(check["id"] == "V-NAME-01" for check in by_platform["claude"]["error"]["checks"])
        assert by_platform["claude"]["error"]["fix"]
        assert by_platform["generic"]["status"] == "succeeded"
        assert os.path.isdir(by_platform["generic"]["dir_path"])
        assert _digest_tree(artifact.dir_path) == before
        assert len(result["items"]) == 2
    finally:
        env.db.close_all()


def test_batch_cancel_marks_remaining(tmp_path):
    env, service, artifact = _setup(tmp_path)

    class _Cancelled:
        def is_set(self):
            return True

    try:
        result = ExportBatch(service, env.registry).run(
            artifact,
            ["claude", "generic"],
            ExportOptions(mode="zip"),
            cancel_token=_Cancelled(),
        )
        assert result["cancelled"] is True
        assert result["summary"] == {"total": 2, "succeeded": 0, "failed": 0, "cancelled": 2}
        assert all(item["status"] == "cancelled" for item in result["items"])
        assert all(item["dir_path"] is None for item in result["items"])
    finally:
        env.db.close_all()


def test_batch_repeat_export_keeps_previous_and_source(tmp_path):
    env, service, artifact = _setup(tmp_path, name="repeat-demo")
    before = _digest_tree(artifact.dir_path)
    try:
        batch = ExportBatch(service, env.registry)
        first = batch.run(artifact, ["claude"], ExportOptions(mode="zip"))
        second = batch.run(artifact, ["claude"], ExportOptions(mode="zip"))
        first_zip = first["items"][0]["zip_path"]
        second_zip = second["items"][0]["zip_path"]
        assert first_zip != second_zip
        assert os.path.isfile(first_zip)
        assert os.path.isfile(second_zip)
        assert os.path.basename(second_zip).startswith("repeat-demo")
        assert _digest_tree(artifact.dir_path) == before
    finally:
        env.db.close_all()