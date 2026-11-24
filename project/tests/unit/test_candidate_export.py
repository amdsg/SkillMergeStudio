from __future__ import annotations

import pytest

from skillmerge.services.exporter.export_service import ExportOptions, ExportService
from skillmerge.services.exporter.validate import _rule_checks
from skillmerge.services.merger.merge_service import MergeOptions
from skillmerge.storage.repos.artifacts_repo import ArtifactsRepo
from skillmerge.util.errors import DomainError
from tests.helpers import build_env, named_skills, scan, write_skill


def _artifact(tmp_path):
    root = str(tmp_path / "skills")
    write_skill(root, "a", "alpha", "源 A", "## 工作流\n\n步骤一：读取数据并校验。")
    write_skill(root, "b", "beta", "源 B", "## 工作流\n\n步骤二：生成报告并保存。")
    env = build_env(tmp_path)
    scan(env, root)
    skills = named_skills(env, ["alpha", "beta"])
    merged = env.merge.merge(skills, MergeOptions(name="candidate-demo", platform="generic"))
    artifact = ArtifactsRepo(env.db).get(merged["artifact_id"])
    return env, ExportService(env.db, env.config, env.registry), artifact


def test_candidate_requires_confirm_and_warns(tmp_path):
    env, service, artifact = _artifact(tmp_path)
    with pytest.raises(DomainError) as captured:
        service.export(artifact, ExportOptions(platform="workbuddy", mode="zip"))
    assert captured.value.code == "PLATFORM_NOT_SELECTABLE"
    result = service.export(
        artifact,
        ExportOptions(platform="workbuddy", mode="zip", confirm_candidate=True),
    )
    ids = {item["id"] for item in result["validation"]}
    assert "V-RULE-02" in ids
    assert "V-RULE-05" in ids
    assert not [item for item in result["validation"] if item["level"] == "error"]
    env.db.close_all()

def test_rule_checks_candidate_and_unreachable():
    candidate = {
        "verification_status": "unknown",
        "evidence_level": "candidate_rules",
        "source": "unknown",
        "verified_at": "unknown",
        "last_verified_at": "2026-01-01",
        "limits_source": "legacy_limits",
    }
    ids = {item["id"] for item in _rule_checks(candidate, "pre")}
    assert {"V-RULE-02", "V-RULE-03", "V-RULE-05"}.issubset(ids)
    unreachable = dict(candidate, evidence_level="failed_unreachable")
    checks = _rule_checks(unreachable, "pre")
    assert any(item["id"] == "V-RULE-04" and item["level"] == "error" for item in checks)