from __future__ import annotations

import os

import pytest

from skillmerge.services.exporter.plan import layout_prefix
from skillmerge.services.exporter.registry import PlatformRegistry
from skillmerge.services.exporter.validate import run_preflight

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGISTRY = PlatformRegistry(os.path.join(ROOT, "platforms"))
SKILL_IDS = [item["id"] for item in REGISTRY.public() if item["kind"] == "skill"]


def make_spec(rule, name="demo-skill", description="演示技能描述。", frontmatter=None, mode=None, prefix=None, fill_required=True):
    text = f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n\n正文\n"
    fm = dict(frontmatter if frontmatter is not None else {})
    for key in rule["frontmatter"].get("required", []) if fill_required else []:
        if key == "name":
            fm[key] = name
        elif key == "description":
            fm[key] = description
        elif key == "description_zh":
            fm[key] = description
        elif key == "description_en":
            fm[key] = "demo skill"
        elif key == "version":
            fm[key] = "1.0.0"
        elif key == "author":
            fm[key] = "unknown"
        elif not fm.get(key):
            fm[key] = "x"
    chosen = mode or ("zip" if rule["package"]["type"] == "zip" else "dir")
    chosen_prefix = layout_prefix(rule, name) if prefix is None else prefix
    return {
        "name": name,
        "description": description,
        "text": text,
        "frontmatter": fm,
        "files": [{"rel_path": "SKILL.md", "size_bytes": len(text.encode("utf-8")), "kind": "document"}],
        "mode": chosen,
        "expected_prefix": chosen_prefix,
        "layout_name": name if chosen in ("zip", "download") else "",
        "planned_entries": [chosen_prefix + "SKILL.md"],
    }


def test_registry_skill_platform_set_is_dynamic():
    entry_ids = {entry.id for entry in REGISTRY.entries() if entry.kind == "skill"}
    assert set(SKILL_IDS) == entry_ids
    assert len(SKILL_IDS) == len(set(SKILL_IDS))
    assert "prompt-only" in {entry.id for entry in REGISTRY.entries()}


@pytest.mark.parametrize("platform", SKILL_IDS)
def test_platform_compliant_and_invalid(platform):
    rule = REGISTRY.require(platform)
    compliant = run_preflight(rule, make_spec(rule))
    assert not [item for item in compliant if item["level"] == "error"], (platform, compliant)

    long_name = "a" * (int(rule["name"]["max_length"]) + 5)
    name_checks = run_preflight(rule, make_spec(rule, name=long_name))
    assert "V-NAME-01" in {item["id"] for item in name_checks}

    long_desc = "d" * (int(rule["description"]["max_chars"]) + 5)
    desc_checks = run_preflight(rule, make_spec(rule, description=long_desc))
    assert "V-DESC-01" in {item["id"] for item in desc_checks}

    missing_checks = run_preflight(rule, make_spec(rule, frontmatter={}, mode="zip", fill_required=False))
    assert "V-FM-01" in {item["id"] for item in missing_checks}

    zip_checks = run_preflight(
        rule,
        make_spec(rule, mode="zip", prefix="other/"),
    )
    assert "V-ZIP-01" in {item["id"] for item in zip_checks}