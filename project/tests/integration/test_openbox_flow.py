from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def report():
    spec = importlib.util.spec_from_file_location("check_openbox", ROOT / "tools" / "check_openbox.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    code, payload, _target = module.run_check(cleanup=True)
    assert code == 0, payload
    return payload


def test_clean_env_five_steps(report):
    assert report["verdict"] == "pass"
    assert len(report["steps"]) == 5
    assert all(step["verdict"] == "pass" for step in report["steps"])
    assert [step["id"] for step in report["steps"]] == ["scan", "classify", "merge", "export", "validate"]


def test_no_ai_key_still_classifies(report):
    assert report["env"]["api_key_present"] is False
    by_id = {step["id"]: step for step in report["steps"]}
    assert by_id["classify"]["verdict"] == "pass"


def test_ai_fallback_indicated(report):
    assert report["ai_fallback"]["activated"] is True
    assert report["ai_fallback"]["indicated"] is True
    assert report["ai_fallback"]["source"] == "keyword"


def test_import_graph_only_stdlib(report):
    assert report["import_graph"]["only_stdlib_and_skillmerge"] is True
    assert report["import_graph"]["third_party"] == []


def test_hash_stable_after_dev_deps(report):
    stability = report["hash_stability"]
    assert stability["equal"] is True
    assert stability["baseline"] == stability["after_dev_deps"]
    assert stability["method"] == "revalidate_same_export"


def test_report_contract_fields(report):
    for field in (
        "schema_version",
        "started_at",
        "finished_at",
        "env",
        "import_graph",
        "ai_fallback",
        "steps",
        "artifacts",
        "hash_stability",
        "verdict",
    ):
        assert field in report
    assert report["artifacts"]["file_hashes"]
    assert report["artifacts"]["manifest_sha256"]