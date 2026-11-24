from __future__ import annotations

import json
import os
import shutil

import pytest

from skillmerge.services.exporter.platform_registry.schema_rules import (
    load_schema,
    validate_aliases,
    validate_baseline,
    validate_entry,
)
from skillmerge.util.errors import DomainError

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLATFORMS = os.path.join(ROOT, "platforms")


def verified_entry():
    return {
        "rule_schema_version": 2,
        "id": "demo",
        "label": "Demo",
        "kind": "skill",
        "group": "通用",
        "origin": "new",
        "batch": "test",
        "source": "https://example.com/demo",
        "source_type": "official_docs",
        "verification_status": "verified",
        "evidence_level": "verified",
        "verified_at": "2026-11-22",
        "last_verified_at": "2026-11-22",
        "unknown_fields": [],
        "notes": "",
        "aliases": [],
        "name": {"pattern": "^[a-z]+$", "max_length": 64, "forbidden_parts": []},
        "description": {"max_chars": 200, "style": "free"},
        "skill_md": {"max_lines": 500, "max_bytes": 32768},
        "bundle": {"max_mb": 30, "max_files": 200, "max_file_mb": 10},
        "package": {"type": "dir", "wrap": False, "skill_md_path": "SKILL.md"},
        "frontmatter": {"required": ["name", "description"], "defaults": {"version": "1.0.0"}},
        "install": {"global": "", "project": ""},
    }


def candidate_entry():
    entry = verified_entry()
    entry.update(
        {
            "origin": "new",
            "source": None,
            "verification_status": "unknown",
            "evidence_level": "candidate_rules",
            "verified_at": None,
            "last_verified_at": None,
            "unknown_fields": ["name", "description", "bundle"],
            "notes": "未核验，仅候选",
        }
    )
    for field in ("name", "description", "skill_md", "bundle", "package", "frontmatter", "install"):
        entry[field] = None
    return entry


def test_schema_loads_and_valid_entries_pass():
    schema = load_schema(os.path.join(PLATFORMS, "schema.json"))
    assert schema["schema_version"] == 2
    assert not validate_entry(verified_entry(), schema, "demo.json")
    assert not validate_entry(candidate_entry(), schema, "demo.json")


def test_schema_rejects_missing_enum_and_conditional_fields():
    schema = load_schema(os.path.join(PLATFORMS, "schema.json"))
    without = verified_entry()
    without.pop("group")
    assert "C-02" in {item["code"] for item in validate_entry(without, schema, "demo.json")}
    bad_enum = verified_entry()
    bad_enum["kind"] = "plugin"
    assert "C-06" in {item["code"] for item in validate_entry(bad_enum, schema, "demo.json")}
    no_source = verified_entry()
    no_source["source"] = None
    assert "C-11" in {item["code"] for item in validate_entry(no_source, schema, "demo.json")}
    candidate_with_body = candidate_entry()
    candidate_with_body["name"] = {"pattern": "^x$", "max_length": 1, "forbidden_parts": []}
    assert "C-13" in {item["code"] for item in validate_entry(candidate_with_body, schema, "demo.json")}
    forbidden = verified_entry()
    forbidden["evidence_level"] = "discovery_source"
    assert "C-18" in {item["code"] for item in validate_entry(forbidden, schema, "demo.json")}


def test_alias_and_baseline_checks():
    schema = load_schema(os.path.join(PLATFORMS, "schema.json"))
    first = candidate_entry()
    first["id"] = "one"
    first["label"] = "One"
    first["aliases"] = ["shared"]
    second = candidate_entry()
    second["id"] = "two"
    second["label"] = "Two"
    second["aliases"] = ["shared"]
    assert "C-14" in {item["code"] for item in validate_aliases([first, second])}
    conflict = candidate_entry()
    conflict["id"] = "three"
    conflict["label"] = "Three"
    conflict["aliases"] = ["two"]
    assert "C-14" in {item["code"] for item in validate_aliases([first, second, conflict])}
    missing = validate_baseline([{"id": "generic"}], schema)
    assert missing and missing[0]["code"] == "C-19"


def test_loader_rejects_invalid_file(tmp_path):
    directory = str(tmp_path / "platforms")
    os.makedirs(directory)
    shutil.copyfile(os.path.join(PLATFORMS, "schema.json"), os.path.join(directory, "schema.json"))
    with open(os.path.join(directory, "bad.json"), "w", encoding="utf-8") as handle:
        json.dump({"id": "bad"}, handle)
    from skillmerge.services.exporter.platform_registry.loader import load_registry

    with pytest.raises(DomainError):
        load_registry(directory)