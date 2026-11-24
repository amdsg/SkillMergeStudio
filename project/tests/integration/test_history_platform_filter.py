from __future__ import annotations

from skillmerge.services.exporter.export_service import ExportOptions, ExportService
from skillmerge.services.history.history_service import list_history
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
    merged = env.merge.merge(skills, MergeOptions(name="history-demo", platform="generic"))
    artifact = ArtifactsRepo(env.db).get(merged["artifact_id"])
    service = ExportService(env.db, env.config, env.registry)
    return env, service, artifact


def _export_three(service, artifact):
    return [
        service.export(artifact, ExportOptions(platform="claude", mode="zip")),
        service.export(artifact, ExportOptions(platform="workbuddy", mode="zip", confirm_candidate=True)),
        service.export(artifact, ExportOptions(platform="codex", mode="dir", confirm_candidate=True)),
    ]


def test_history_platform_filter(tmp_path):
    env, service, artifact = _setup(tmp_path)
    try:
        _export_three(service, artifact)
        repo = ArtifactsRepo(env.db)
        all_items = list_history(repo, 50, 0)
        assert all_items["page"]["total"] == 4
        assert len(all_items["items"]) == 4

        claude = list_history(repo, 50, 0, None, "claude")
        assert claude["page"] == {"limit": 50, "offset": 0, "total": 1}
        assert len(claude["items"]) == 1
        assert claude["items"][0]["platform"] == "claude"

        workbuddy = list_history(repo, 50, 0, None, "workbuddy")
        assert workbuddy["page"]["total"] == 1
        assert workbuddy["items"][0]["platform"] == "workbuddy"

        missing = list_history(repo, 50, 0, None, "no-such-platform")
        assert missing["page"]["total"] == 0
        assert missing["items"] == []

        page = list_history(repo, 1, 1, None, "claude")
        assert page["page"] == {"limit": 1, "offset": 1, "total": 1}
        assert page["items"] == []
    finally:
        env.db.close_all()


def test_history_default_behavior_unchanged(tmp_path):
    env, service, artifact = _setup(tmp_path)
    try:
        _export_three(service, artifact)
        repo = ArtifactsRepo(env.db)
        default = list_history(repo, 50, 0)
        explicit_empty = list_history(repo, 50, 0, None, "")
        assert default["page"] == explicit_empty["page"] == {"limit": 50, "offset": 0, "total": 4}
        assert [item["id"] for item in default["items"]] == [item["id"] for item in explicit_empty["items"]]
    finally:
        env.db.close_all()