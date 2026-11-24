from __future__ import annotations

from skillmerge.services.exporter.platform_registry.format import format_info, manifest_format
from skillmerge.services.exporter.platform_registry.query import _limits
from skillmerge.services.exporter.registry import PlatformRegistry


def _registry():
    return PlatformRegistry("platforms")


def test_all_platforms_have_format():
    registry = _registry()
    entries = registry.entries()
    assert len(entries) == 28
    verified = 0
    for entry in entries:
        info = format_info(entry)
        assert info["package_type"] in {"dir", "zip", "prompt"}
        assert info["rule_source"] in {"verified", "legacy_limits"}
        assert info["rule_status"] in {"verified", "candidate"}
        assert info["skill_md_path"]
        assert isinstance(info["install_scopes"], list)
        assert info["requires_confirm"] == (entry.verification_status == "unknown")
        assert info["limits_source"] == info["rule_source"]
        if entry.verification_status == "verified":
            verified += 1
    assert verified == 3


def test_verified_samples():
    registry = _registry()
    claude = format_info(registry.entry("claude"))
    assert claude == {
        "package_type": "zip",
        "wrap": False,
        "skill_md_path": "<name>/SKILL.md",
        "install_scopes": ["global", "project"],
        "rule_source": "verified",
        "rule_status": "verified",
        "requires_confirm": False,
        "limits_source": "verified",
    }
    generic = format_info(registry.entry("generic"))
    assert generic["package_type"] == "dir"
    assert generic["skill_md_path"] == "SKILL.md"
    assert generic["install_scopes"] == []


def test_candidate_samples():
    registry = _registry()
    workbuddy = format_info(registry.entry("workbuddy"))
    assert workbuddy == {
        "package_type": "zip",
        "wrap": True,
        "skill_md_path": "skills/<name>/SKILL.md",
        "install_scopes": [],
        "rule_source": "legacy_limits",
        "rule_status": "candidate",
        "requires_confirm": True,
        "limits_source": "legacy_limits",
    }
    codex = format_info(registry.entry("codex"))
    assert codex["package_type"] == "dir"
    assert codex["skill_md_path"] == "SKILL.md"
    assert _limits(registry.entry("workbuddy")) is None
    assert registry.entry("workbuddy").verification_status == "unknown"


def test_prompt_sample():
    info = format_info(_registry().entry("prompt-only"))
    assert info["package_type"] == "prompt"
    assert info["skill_md_path"] == "prompt.md"


def test_manifest_format_samples():
    registry = _registry()
    claude = manifest_format(registry.entry("claude").as_rule())
    assert claude["package_type"] == "zip"
    assert claude["install_available"] is True
    assert claude["rule_status"] == "verified"
    assert claude["limits_source"] == "verified"
    workbuddy = manifest_format(registry.entry("workbuddy").as_rule())
    assert workbuddy["wrap"] is True
    assert workbuddy["skill_md_path"] == "skills/<name>/SKILL.md"
    assert workbuddy["install_available"] is False
    assert workbuddy["rule_status"] == "candidate"
    assert workbuddy["limits_source"] == "legacy_limits"