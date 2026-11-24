from __future__ import annotations

import os
import shutil

import pytest

from skillmerge.services.history.rebuild import RebuildService
from skillmerge.services.history.undo import undo_artifact
from skillmerge.services.merger.merge_service import MergeOptions
from skillmerge.storage.repos.artifacts_repo import ArtifactsRepo
from skillmerge.util.errors import DomainError
from tests.helpers import build_env, named_skills, scan, write_skill


def _merge(tmp_path):
    root = str(tmp_path / "skills")
    write_skill(root, "a", "alpha", "源 A", "## 工作流\n\n步骤一：读取并校验。")
    write_skill(root, "b", "beta", "源 B", "## 工作流\n\n步骤二：生成报告。")
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta"])
    artifact = env.merge.merge(skills, MergeOptions(name="history-demo", platform="generic"))
    repo = ArtifactsRepo(env.db)
    return env, repo, repo.get(artifact["artifact_id"]), root


def test_undo_requires_unchanged_and_moves_to_trash(tmp_path):
    env, repo, artifact, _root = _merge(tmp_path)
    target = os.path.join(artifact.dir_path, "SKILL.md")
    with open(target, "ab") as handle:
        handle.write(b"\n")
    with pytest.raises(DomainError) as captured:
        undo_artifact(repo, artifact, env.config.save_dir)
    assert captured.value.code == "ARTIFACT_MODIFIED"
    os.remove(target)
    shutil.copyfile(os.path.join(artifact.dir_path, "merge_plan.json"), target)
    with pytest.raises(DomainError):
        undo_artifact(repo, artifact, env.config.save_dir)
    env.db.close_all()


def test_undo_success_and_trash_findable(tmp_path):
    env, repo, artifact, _root = _merge(tmp_path)
    result = undo_artifact(repo, artifact, env.config.save_dir)
    assert not os.path.exists(artifact.dir_path)
    assert os.path.isdir(result["trash_path"])
    updated = repo.get(artifact.id)
    assert updated.status == "undone"
    assert updated.undone_at
    env.db.close_all()


def test_rebuild_diffs_changed_sources(tmp_path):
    env, repo, artifact, root = _merge(tmp_path)
    with open(os.path.join(root, "a", "SKILL.md"), "a", encoding="utf-8") as handle:
        handle.write("\n\n## 新增章节\n\n这是新增内容。\n")
    service = RebuildService(env.merge, env.repo, repo)
    result = service.rebuild(artifact)
    assert result["source_updated"] is True
    assert result["artifact"]["artifact_id"] != artifact.id
    ops = {item["op"] for item in result["diff"]}
    assert "add" in ops
    assert repo.get(artifact.id).status == "active"
    env.db.close_all()