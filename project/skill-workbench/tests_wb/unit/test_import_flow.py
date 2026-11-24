import json
import sys
from pathlib import Path

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.api import import_endpoint as endpoint_module  # noqa: E402
from agent.core import import_detect, import_map, intermediate  # noqa: E402

GENERIC = """# Generic Skill

Summary line.

## Capabilities
- summarize text

## Instructions
1. Read the input.
2. Write the summary.
"""

GPT = """# GPT Skill

## Role
Summary line.

## Instructions
1. Read the input.
"""

DEEPSEEK = """# DeepSeek Skill

## 角色
Summary line.

## 能力
- summarize text

## 流程
1. Read the input.
"""


def test_detect_explicit_and_unknown():
    assert import_detect.detect("anything", "deepseek")["profile_id"] == "deepseek"
    result = import_detect.detect("plain text without headings")
    assert result["profile_id"] == "generic_markdown"
    assert result["format_recognized"] is False


def test_detect_structural_signature():
    result = import_detect.detect(GPT)
    assert result["profile_id"] == "gpt"
    assert result["format_recognized"] is True


def test_three_sources_are_isomorphic():
    docs = []
    for text, profile in ((GENERIC, "generic_markdown"), (GPT, "gpt"), (DEEPSEEK, "deepseek")):
        doc, report = import_map.build(text, profile, True, source=f"fixture/{profile}")
        assert intermediate.validate(doc) == []
        assert report["summary"]["mapped"] >= 1
        docs.append(doc)
    assert set(docs[0]) == set(docs[1]) == set(docs[2])
    assert set(docs[0]["identity"]) == set(docs[1]["identity"]) == set(docs[2]["identity"])


def test_missing_required_is_synthesized_unknown():
    doc, report = import_map.build("plain text", "generic_markdown", False)
    assert intermediate.validate(doc) == []
    synthesized = {(item["target_path"], item["value"], item["origin"]) for item in report["synthesized"]}
    assert ("capabilities[0]", "unknown", "unknown") in synthesized
    assert ("instructions[0]", "unknown", "unknown") in synthesized


def test_dropped_limit_and_vendor_field():
    text = """---
x_vendor_tag: hidden
version: 1.0.0
---

# Skill

Summary.

## Instructions
1. 最多 8000 字符
2. do it
"""
    doc, report = import_map.build(text, "generic_markdown", True)
    assert intermediate.validate(doc) == []
    reasons = {(item["reason_code"], item["loses_capability"]) for item in report["dropped"]}
    assert ("unmapped_field", False) in reasons
    assert ("limit_value", True) in reasons


def test_import_endpoint_dry_run_and_idempotency(tmp_path, monkeypatch):
    monkeypatch.setattr(endpoint_module, "IMPORTS", tmp_path / "imports")
    dry = json.dumps({"text": GENERIC, "dry_run": True}).encode("utf-8")
    result = endpoint_module.import_endpoint({}, dry, "r-1")
    assert result["dry_run"] is True
    assert result["writes"] == 0
    assert not (tmp_path / "imports").exists()

    body = json.dumps({"text": GENERIC, "dry_run": False, "idempotency_key": "key-123456"}).encode("utf-8")
    first = endpoint_module.import_endpoint({}, body, "r-2")
    assert first["reused"] is False
    assert (tmp_path / "imports" / first["import_id"] / "intermediate.json").is_file()
    second = endpoint_module.import_endpoint({}, body, "r-3")
    assert second["reused"] is True