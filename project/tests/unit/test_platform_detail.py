from __future__ import annotations

from skillmerge.services.exporter.platform_registry.detail import build_detail
from skillmerge.services.exporter.registry import PlatformRegistry


def test_detail_verified_and_candidate():
    registry = PlatformRegistry("platforms")
    claude = build_detail(registry, "claude", registry.discovery_records())
    assert claude["platform"]["verification_status"] == "verified"
    assert claude["platform"]["limits"]["bundle_max_mb"] == 30
    assert claude["platform"]["requires_confirm"] is False
    assert claude["verification"]["latest"] is None
    workbuddy = build_detail(registry, "workbuddy", registry.discovery_records())
    assert workbuddy["platform"]["verification_status"] == "unknown"
    assert workbuddy["platform"]["limits"] is None
    assert workbuddy["platform"]["legacy_limits_present"] is True
    assert workbuddy["platform"]["requires_confirm"] is True


def test_detail_evidence_matching_is_exact():
    registry = PlatformRegistry("platforms")
    records = [
        {
            "key": "claude-skills",
            "label": "Claude",
            "url": "https://code.claude.com/docs/en/skills",
            "final_url": "https://code.claude.com/docs/en/skills",
            "status": 200,
            "error": "",
            "markers": {"skill_md": True},
        }
    ]
    detail = build_detail(registry, "claude", records)
    assert detail["evidence_pages"] == []
    records[0]["key"] = "claude"
    detail = build_detail(registry, "claude", records)
    assert len(detail["evidence_pages"]) == 1
    assert detail["evidence_pages"][0]["match"] == "key"