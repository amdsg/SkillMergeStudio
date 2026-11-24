from __future__ import annotations

import os

from skillmerge.services.exporter.platform_registry.migrate_v1 import normalize_v1
from skillmerge.services.exporter.registry import PlatformRegistry

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLATFORMS = os.path.join(ROOT, "platforms")


def test_baseline_registry_counts_and_ids():
    registry = PlatformRegistry(PLATFORMS)
    counts = registry.counts()
    assert counts.total == 28
    assert counts.verified == 3
    assert counts.verified_official == 1
    assert counts.local_contract == 2
    assert counts.candidate == 25
    assert counts.unknown == 25
    assert counts.skill == 27
    assert counts.prompt == 1
    ids = {entry.id for entry in registry.entries()}
    assert len(ids) == 28
    assert "claude" in ids and "prompt-only" in ids


def test_v1_candidate_moves_body_to_legacy_limits():
    raw = {
        "rule_schema_version": 1,
        "id": "workbuddy",
        "label": "WorkBuddy",
        "kind": "skill",
        "source": "unknown",
        "verified_at": "unknown",
        "name": {"pattern": "^x$", "max_length": 10, "forbidden_parts": []},
        "description": {"max_chars": 100, "style": "x"},
        "skill_md": {"max_lines": 10, "max_bytes": 100},
        "bundle": {"max_mb": 3, "max_files": 10, "max_file_mb": 3},
        "package": {"type": "zip", "wrap": True, "skill_md_path": "skills/<name>/SKILL.md"},
        "frontmatter": {"required": ["name"], "defaults": {}},
        "install": {"global": "", "project": ""},
        "notes": "",
    }
    normalized = normalize_v1(raw)
    assert normalized["verification_status"] == "unknown"
    assert normalized["evidence_level"] == "candidate_rules"
    assert normalized["source"] is None
    assert normalized["verified_at"] is None
    assert normalized["name"] is None
    assert normalized["legacy_limits"]["package"]["type"] == "zip"
    assert normalized["unknown_fields"]
    assert normalized["origin"] == "baseline"
    assert normalized["group"] == "企业协作"
    assert "v1 兼容读取" in normalized["notes"]


def test_v1_verified_local_contract_keeps_body():
    raw = {
        "rule_schema_version": 1,
        "id": "generic",
        "label": "通用目录",
        "kind": "skill",
        "source": "local://skillmerge/generic",
        "verified_at": "2026-11-22",
        "name": {"pattern": "^x$", "max_length": 10, "forbidden_parts": []},
        "description": {"max_chars": 100, "style": "x"},
        "skill_md": {"max_lines": 10, "max_bytes": 100},
        "bundle": {"max_mb": 3, "max_files": 10, "max_file_mb": 3},
        "package": {"type": "dir", "wrap": False, "skill_md_path": "SKILL.md"},
        "frontmatter": {"required": ["name"], "defaults": {}},
        "install": {"global": "", "project": ""},
        "notes": "local",
    }
    normalized = normalize_v1(raw)
    assert normalized["verification_status"] == "verified"
    assert normalized["source_type"] == "local_contract"
    assert normalized["evidence_level"] == "verified"
    assert normalized["legacy_limits"] is None
    assert normalized["name"]["max_length"] == 10


def test_require_keeps_legacy_export_view():
    registry = PlatformRegistry(PLATFORMS)
    workbuddy = registry.entry("workbuddy")
    assert workbuddy.rule_body is None
    assert workbuddy.legacy_limits is not None
    rule = registry.require("workbuddy")
    assert rule["package"]["type"] == "zip"
    assert rule["verification_status"] == "unknown"
    assert rule["source"] == "unknown"
    claude = registry.require("claude")
    assert claude["verification_status"] == "verified"
    assert claude["source_type"] == "official_docs"