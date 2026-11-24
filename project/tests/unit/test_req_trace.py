from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / ".codeartsdoer/specs/skillmerge_studio/spec.md"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("check_req_trace", ROOT / "tools" / "check_req_trace.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def entries(mod):
    return mod.extract_entries(SPEC_PATH.read_text(encoding="utf-8"))


def test_t01_extract_338_unique(mod, entries):
    assert len(entries) == 341
    assert len({item["req"] for item in entries}) == 341
    assert {item["prio"] for item in entries} == {"P0", "P1", "P2"}


def test_t02_cross_reference_not_counted(mod):
    text = "- **REQ-AAA-001** [P0] x\n见 REQ-AAA-001\n"
    assert len(mod.extract_entries(text)) == 1


def test_t03_duplicate_not_silently_deduped(mod):
    text = "- **REQ-AAA-001** [P0] x\n- **REQ-AAA-001** [P0] y\n"
    assert len(mod.extract_entries(text)) == 2


def test_t04_claims_match(mod):
    assert mod.parse_claims(SPEC_PATH.read_text(encoding="utf-8")) == {
        "total": 341,
        "P0": 241,
        "P1": 88,
        "P2": 12,
    }


def test_t05_claims_mismatch_detected(mod):
    claims = mod.parse_claims("需求条目总数：**337**\n**P0：1 条**、**P1：2 条**、**P2：3 条**")
    assert claims["total"] == 337


def test_t06_write_is_idempotent(mod, monkeypatch, tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("- **REQ-AAA-001** [P0] x\n- **REQ-AAA-002** [P1] y\n", encoding="utf-8")
    map_path = tmp_path / "req-map.json"
    monkeypatch.setattr(mod, "SPEC", spec)
    monkeypatch.setattr(mod, "MAP_PATH", map_path)
    entries = mod.extract_entries(spec.read_text(encoding="utf-8"))
    assert mod.write_skeleton(entries, {"total": 2}) == 0
    first = map_path.read_text(encoding="utf-8")
    assert mod.write_skeleton(entries, {"total": 2}) == 0
    assert map_path.read_text(encoding="utf-8") == first
    assert "verified" not in first


def test_t07_set_missing(mod, entries):
    data = {
        "spec_entries": len(entries),
        "spec_digest": mod.digest(SPEC_PATH.read_text(encoding="utf-8")),
        "items": [{"req": "REQ-VER-001", "prio": "P0", "status": "not_started", "anchors": []}],
    }
    errors, _warnings = mod.check_map(data, entries, set(), False)
    assert any("M6-SET-MISSING" in item for item in errors)


def test_t08_p0_without_required_anchor(mod):
    data = {
        "spec_entries": 1,
        "spec_digest": mod.digest("x"),
        "items": [{"req": "REQ-AAA-001", "prio": "P0", "status": "not_started", "anchors": []}],
    }
    errors, _warnings = mod.check_map(data, [{"req": "REQ-AAA-001", "prio": "P0"}], set(), False)
    assert any("M6-P0-NO-ANCHOR" in item for item in errors)


def test_t09_pytest_anchor_resolution(mod):
    nodes = {"tests/a.py::test_x"}
    assert mod.resolve_anchor({"kind": "pytest", "id": "tests/a.py::test_x"}, nodes)
    assert not mod.resolve_anchor({"kind": "pytest", "id": "tests/a.py::test_y"}, nodes)


def test_t10_manual_anchor_resolution(mod, monkeypatch, tmp_path):
    doc = tmp_path / "m.md"
    doc.write_text("x\n- [ ] B-01\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.resolve_anchor({"kind": "manual", "id": "m.md#L2"}, set())
    assert not mod.resolve_anchor({"kind": "manual", "id": "m.md#L999"}, set())


def test_t11_shared_nodes_is_warning(mod, entries):
    anchor = {"kind": "script", "id": "README.txt", "level": "static", "required": True}
    data = {
        "spec_entries": 2,
        "spec_digest": mod.digest(SPEC_PATH.read_text(encoding="utf-8")),
        "items": [
            {"req": "REQ-VER-001", "prio": "P0", "status": "not_started", "anchors": [anchor]},
            {"req": "REQ-VER-002", "prio": "P0", "status": "not_started", "anchors": [anchor]},
        ],
    }
    _errors, warnings = mod.check_map(data, [{"req": "REQ-VER-001"}, {"req": "REQ-VER-002"}], set(), False)
    assert any("M6-SHARED-NODES" in item for item in warnings)


def test_t12_collect_failure_is_structured(mod, monkeypatch):
    def boom(*args, **kwargs):
        raise TimeoutError("timeout")

    monkeypatch.setattr(mod.subprocess, "run", boom)
    result = mod.collect_nodes()
    assert result["ok"] is False
    assert result["nodes"] == set()


def test_t13_verified_without_evidence_downgrades(mod):
    item = {"status": "verified", "evidence": [], "anchors": []}
    assert mod.derive_status(item, set()) == "partial"


def test_t14_blocked_without_missing(mod, entries):
    data = {
        "spec_entries": 1,
        "spec_digest": mod.digest(SPEC_PATH.read_text(encoding="utf-8")),
        "items": [{"req": "REQ-VER-007", "prio": "P0", "status": "blocked", "missing": [], "anchors": []}],
    }
    errors, _warnings = mod.check_map(data, [{"req": "REQ-VER-007"}], set(), False)
    assert any("M6-BLOCKED-NO-REASON" in item for item in errors)


def test_t15_exempt_without_basis(mod, entries):
    data = {
        "spec_entries": 1,
        "spec_digest": mod.digest(SPEC_PATH.read_text(encoding="utf-8")),
        "items": [
            {"req": "REQ-VER-017", "prio": "P2", "status": "exempt", "basis_req": "", "anchors": []}
        ],
    }
    errors, _warnings = mod.check_map(data, [{"req": "REQ-VER-017"}], set(), False)
    assert any("M6-EXEMPT-ILLEGAL" in item for item in errors)


def test_t16_status_never_upgrades(mod):
    item = {"status": "partial", "evidence": ["x"], "anchors": []}
    assert mod.derive_status(item, set()) == "partial"


def test_t17_schema_enum(mod, entries):
    data = {
        "spec_entries": 1,
        "spec_digest": mod.digest(SPEC_PATH.read_text(encoding="utf-8")),
        "items": [{"req": "REQ-VER-001", "prio": "P0", "status": "weird", "anchors": []}],
    }
    errors, _warnings = mod.check_map(data, [{"req": "REQ-VER-001"}], set(), False)
    assert any("M6-SCHEMA-ENUM" in item for item in errors)


def test_t18_wording_negation_is_info(mod, monkeypatch, tmp_path):
    doc = tmp_path / "README.txt"
    doc.write_text("不得称浏览器已验证\n浏览器已验证\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    issues = mod.check_wording()
    assert len(issues) == 1
    assert "browser-claim" in issues[0]


def test_t19_summary_three_buckets(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(mod, "SUMMARY_MD", tmp_path / "summary.md")
    data = {
        "items": [
            {"req": "A", "status": "verified"},
            {"req": "B", "status": "blocked"},
            {"req": "C", "status": "exempt"},
            {"req": "D", "status": "not_started"},
        ],
        "sampling": {"ratio": 0.2, "ratio_confirmed": False, "records": []},
    }
    payload = mod.render_summary(data, [])
    assert payload["total"] == 4
    assert payload["passed"] == 1
    assert payload["not_executed"] == 2
    assert payload["exempt"] == 1
    assert "pass_rate" not in payload


def test_t20_check_path_is_readonly(mod, entries):
    tracked = [mod.MAP_PATH, mod.SUMMARY_MD]
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked if path.is_file()}
    mod.check_map(mod.load_map(), entries, set(), False)
    after = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in tracked if path.is_file()}
    assert before == after

def test_closure_identity_341(mod):
    data = mod.load_map()
    closure = mod.derive_closure(data)
    assert closure["total"] == 341
    assert closure["closed"] + closure["open"] == 341
    assert closure["identity_ok"] is True
    assert closure["verified"] == 0


def test_closure_identity_violation(mod):
    items = [{"req": f"REQ-X-{i:03d}", "status": "verified", "evidence": ["x"]} for i in range(340)]
    closure = mod.derive_closure({"spec_entries": 341, "items": items})
    assert closure["closed"] == 340
    assert closure["open"] == 0
    assert closure["identity_ok"] is False


def test_acceptance_counts_closed_not_passed(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "SUMMARY_JSON", tmp_path / "summary.json")
    monkeypatch.setattr(mod, "SUMMARY_MD", tmp_path / "summary.md")
    accepted = {
        "req": "REQ-VER-003",
        "status": "exempt",
        "acceptance": {
            "state": "accepted",
            "basis_req": "REQ-CON-012",
            "type": "environment",
            "substitute_evidence": "docs/browser-manual-checklist.md",
            "accepter": "user",
            "accepted_at": "2026-11-22",
            "review_trigger": "browser_dependency_approved",
            "valid_until": "2027-11-22",
        },
    }
    items = [accepted] + [{"req": f"REQ-X-{i:03d}", "status": "not_started"} for i in range(340)]
    closure = mod.derive_closure({"spec_entries": 341, "items": items})
    assert closure["accepted_exempt"] == 1
    assert closure["verified"] == 0
    assert closure["closed"] == 1
    summary = mod.render_summary({"items": items, "sampling": {"records": []}}, [])
    assert summary["passed"] == 0


def test_acceptance_requires_all_fields(mod):
    item = {
        "req": "REQ-VER-003",
        "status": "exempt",
        "acceptance": {"state": "accepted", "basis_req": "REQ-CON-012"},
    }
    errors = mod.check_closure([item], {item["req"]: item})
    assert any("M6-ACCEPT-MISSING-FIELD" in value for value in errors)


def test_pending_acceptance_is_open(mod):
    item = {
        "req": "REQ-VER-003",
        "status": "exempt",
        "acceptance": {"state": "pending_acceptance"},
    }
    closure = mod.derive_closure({"spec_entries": 1, "items": [item]})
    assert closure["closed"] == 0
    assert closure["open"] == 1
    assert closure["open_details"][0]["open_reason"] == "exemption_not_accepted"


def test_acceptance_only_for_exempt(mod):
    item = {"req": "REQ-VER-019", "status": "verified", "acceptance": {"state": "accepted"}}
    errors = mod.check_closure([item], {item["req"]: item})
    assert any("M6-ACCEPT-NOT-EXEMPT" in value for value in errors)


def test_ver019_exempt_is_illegal(mod):
    item = {"req": "REQ-VER-019", "status": "exempt", "basis_req": "REQ-CON-012"}
    errors = mod.check_closure([item], {item["req"]: item})
    assert "M6-EXEMPT-ILLEGAL: REQ-VER-019" in errors


def test_redline_refusal_matrix(mod):
    cmp_item = {
        "req": "REQ-CMP-001",
        "status": "verified",
        "evidence": [{"kind": "platform", "result": "pass"}],
    }
    v11 = {"req": "REQ-VER-011", "status": "verified", "evidence": []}
    v19 = {"req": "REQ-VER-019", "status": "exempt", "basis_req": "REQ-CON-012"}
    items = [cmp_item, v11, v19]
    errors = mod.check_closure(items, {item["req"]: item for item in items})
    assert "M6-CMP-OVERCLAIM" in errors
    assert "M6-REDLINE-VIOLATION#platform" in errors
    assert "M6-REDLINE-VIOLATION#real-dir" in errors
    assert "M6-EXEMPT-ILLEGAL: REQ-VER-019" in errors


def test_open_condition_required(mod):
    item = {"req": "REQ-VER-003", "status": "not_started", "required_condition": ""}
    errors = mod.check_closure([item], {item["req"]: item})
    assert any("M6-OPEN-NO-CONDITION" in value for value in errors)
