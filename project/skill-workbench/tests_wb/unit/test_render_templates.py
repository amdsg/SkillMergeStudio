import sys
from pathlib import Path

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.core import feature_diff, render  # noqa: E402
from agent.http.errors import DomainError  # noqa: E402


SAMPLE = {
    "schema_version": 1,
    "identity": {"name": "Sample", "id": "sample", "version": "1.0.0", "tags": []},
    "intent": {"summary": "Do one thing.", "source_kind": "skill_md"},
    "capabilities": [{"trigger": "on demand", "inputs": ["text"], "outputs": ["text"], "constraints": []}],
    "instructions": [{"step": 1, "text": "Read the input."}],
    "examples": [],
    "resources": [],
    "provenance": {"source": "fixture", "native_targets": ["unknown"], "import_id": "i", "mapping_report_ref": "r"},
}


def test_feature_diff_three_way_and_ack():
    result = feature_diff.classify(["a", "b", "c"], ["a"], {"b": "text only"})
    assert result["counts"] == {"supported": 1, "degraded": 1, "unsupported": 1}
    assert sum(result["counts"].values()) == result["total"] == 3
    assert result["requires_ack"] is True
    with pytest.raises(DomainError) as error:
        feature_diff.require_ack(result, "wrong")
    assert error.value.code == "E_FEATURE_ACK_REQUIRED"
    feature_diff.require_ack(result, result["ack_token"])


def test_render_is_deterministic_and_ordered():
    template = render.load_template("generic")
    first = render.render(SAMPLE, template)
    second = render.render(SAMPLE, template)
    assert first == second
    assert first.index("## Overview") < first.index("## Capabilities") < first.index("## Instructions")
    assert "Do one thing." in first


def test_unknown_target_cannot_have_dedicated_template():
    template = render.load_template("generic")
    template = dict(template)
    template["target_id"] = "some-unknown-target"
    template["evidence_level"] = "unknown"
    assert any("unknown target" in error for error in render.validate_template(template))


def test_limit_values_are_rejected():
    template = dict(render.load_template("generic"))
    template["sections"] = list(template["sections"]) + [{"heading": "Limits", "required": False, "source_field": "unknown"}]
    template["note"] = "最多 8000 字符"
    assert any("limit value" in error for error in render.validate_template(template))