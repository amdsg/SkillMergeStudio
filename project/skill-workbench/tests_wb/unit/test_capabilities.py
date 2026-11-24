import json
import sys
from pathlib import Path

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.api.settings import enable_capability, get_settings  # noqa: E402
from agent.config import runtime  # noqa: E402
from agent.config.defaults import RISK_ACK_VERSION  # noqa: E402
from agent.http.errors import DomainError  # noqa: E402


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime, "SETTINGS_PATH", tmp_path / "settings.json")
    return tmp_path


def test_is_enabled_defaults_false(isolated):
    assert runtime.is_enabled("real_write") is False


def test_enable_requires_matching_risk_ack(isolated):
    with pytest.raises(ValueError):
        runtime.enable("real_write", "", "user")


def test_enable_then_is_enabled(isolated):
    runtime.enable("real_write", RISK_ACK_VERSION, "user")
    assert runtime.is_enabled("real_write") is True


def test_snapshot_carries_audit_fields(isolated):
    runtime.enable("real_write", RISK_ACK_VERSION, "alice")
    cap = next(c for c in runtime.snapshot() if c["capability_id"] == "real_write")
    assert cap["enabled"] is True
    assert cap["enabled_by"] == "alice"
    assert cap["enabled_at"]
    assert cap["risk_ack"] == RISK_ACK_VERSION
    assert cap["unverified"] is False


def test_unverified_override_never_takes_effect(isolated):
    runtime._save({"capabilities": {"real_write": {"enabled": True}}})
    assert runtime.is_enabled("real_write") is False
    cap = next(c for c in runtime.snapshot() if c["capability_id"] == "real_write")
    assert cap["unverified"] is True


def test_settings_endpoint_returns_capabilities(isolated):
    result = get_settings({}, b"", "")
    assert result["risk_ack_version"] == RISK_ACK_VERSION
    assert len(result["capabilities"]) == 5


def test_enable_capability_endpoint_requires_risk_ack(isolated):
    with pytest.raises(DomainError) as exc:
        enable_capability({"id": "real_write"}, json.dumps({"risk_ack": ""}).encode(), "")
    assert exc.value.code == "E_RISK_ACK_REQUIRED"


def test_enable_capability_endpoint_success(isolated):
    result = enable_capability({"id": "real_write"}, json.dumps({"risk_ack": RISK_ACK_VERSION}).encode(), "")
    assert result["enabled"] is True
    assert runtime.is_enabled("real_write") is True


def test_enable_capability_unknown_id(isolated):
    with pytest.raises(DomainError) as exc:
        enable_capability({"id": "nope"}, b"", "")
    assert exc.value.code == "E_NOT_FOUND"
