import importlib.util
import json
import sys
from pathlib import Path

WB_ROOT = Path(__file__).resolve().parents[2]
if str(WB_ROOT) not in sys.path:
    sys.path.insert(0, str(WB_ROOT))

TARGETS = WB_ROOT / "agent" / "adapters" / "targets.json"
GROUPS = WB_ROOT / "agent" / "adapters" / "target_groups.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, WB_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registry_counts_identity():
    items = load(TARGETS)
    enabled = [item for item in items if item.get("enabled", True)]
    verified = [item for item in enabled if item["evidence_level"] == "verified"]
    assert len(enabled) == len(verified) + len([i for i in enabled if i["evidence_level"] == "candidate"]) + len([i for i in enabled if i["evidence_level"] == "unknown"])
    assert len(verified) == 3
    assert len([item for item in verified if item.get("evidence_subtype") == "official"]) == 1
    assert len([item for item in verified if item.get("evidence_subtype") == "local_contract"]) == 2


def test_registry_accepts_current_data():
    gate = load_module("wb_registry_gate", "tools/check_adapter_registry.py")
    items = load(TARGETS)
    groups = load(GROUPS)
    tool_ids = {"claude_code"}
    errors, counts = gate.validate(items, groups, tool_ids)
    assert errors == []
    assert counts["total"] == 25


def test_registry_duplicate_id_is_rejected():
    gate = load_module("wb_registry_gate", "tools/check_adapter_registry.py")
    items = load(TARGETS)
    groups = load(GROUPS)
    bad = items + [dict(items[0])]
    errors, _ = gate.validate(bad, groups, {"claude_code"})
    assert any("duplicate id" in error for error in errors)


def test_unknown_with_source_is_rejected():
    gate = load_module("wb_registry_gate", "tools/check_adapter_registry.py")
    items = load(TARGETS)
    bad = [dict(item) for item in items]
    target = next(item for item in bad if item["evidence_level"] == "unknown")
    target["source"] = "https://example.invalid/spec"
    errors, _ = gate.validate(bad, load(GROUPS), {"claude_code"})
    assert any("unknown must have no source" in error for error in errors)


def test_open_registry_gate_passes():
    gate = load_module("wb_open_gate", "tools/check_target_registry_open.py")
    assert gate.main(["--check"]) == 0


def test_defaults_are_all_off():
    defaults = load_module("wb_defaults", "agent/config/defaults.py")
    assert all(value is False for value in defaults.CAPABILITIES.values())


def test_i18n_dictionary_parity():
    gate = load_module("wb_i18n_gate", "tools/check_i18n_wb.py")
    zh = gate.entries(WB_ROOT / "extension" / "lib" / "i18n" / "zh.js")
    en = gate.entries(WB_ROOT / "extension" / "lib" / "i18n" / "en.js")
    assert zh
    assert set(zh) == set(en)
    assert not any(gate.CJK.search(value) for value in en.values())


def test_inheritance_is_blocked():
    record = load(WB_ROOT / "agent" / "store" / "records" / "inheritance.json")
    assert record["state"] == "blocked"
    assert record["reason_code"] == "inheritance_source_missing"
    assert record["digest"] is None


def test_applicability_unknown_not_universal():
    module = load_module("wb_applicability", "agent/core/applicability.py")
    result = module.resolve(None)
    assert result["mode"] == "unknown"
    assert result["reason_code"] == "not_fetched"
    assert module.requires_ack({"mode": "unknown", "targets": []}, "claude") is False


def test_tool_match_requires_detected():
    module = load_module("wb_tool_match", "agent/core/tool_match.py")
    hints = [{"target_id": "claude", "tool_ids": ["claude_code"]}]
    tools = [{"tool_id": "claude_code", "state": "unknown", "matched_path": ""}]
    result = module.recommend("claude", hints, tools)
    assert result["recommended_tool_id"] is None
    assert result["reason_code"] == "tool_evidence_unknown"
    detected = [{"tool_id": "claude_code", "state": "detected", "matched_path": "C:/tools/claude"}]
    result = module.recommend("claude", hints, detected)
    assert result["recommended_tool_id"] == "claude_code"