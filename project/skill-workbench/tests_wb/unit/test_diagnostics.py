import sys
from pathlib import Path

import pytest

WB = Path(__file__).resolve().parents[2]
if str(WB) not in sys.path:
    sys.path.insert(0, str(WB))

from agent.api.diagnostics import MAX_BYTES, get_diagnostics  # noqa: E402
from agent.core import audit  # noqa: E402
from agent.core.redact import redact_obj, redact_text  # noqa: E402
from agent.http.errors import DomainError  # noqa: E402


def setup_function():
    audit.clear()


def test_redact_token_and_home():
    text = "token=ghp_" + "a" * 36 + " path=C:\\Users\\alice\\skills key=sk-" + "b" * 24
    redacted = redact_text(text)
    assert "ghp_" not in redacted
    assert "alice" not in redacted
    assert "sk-" not in redacted
    assert "<TOKEN>" in redacted
    assert "<home>" in redacted


def test_redact_nested():
    value = {"headers": {"Authorization": "Bearer abcdefghijklmnop"}, "path": "/home/u/x"}
    redacted = redact_obj(value)
    assert "abcdefghijklmnop" not in str(redacted)
    assert "/home/u" not in str(redacted)


def test_timeline_filters_request_id_and_redacts():
    audit.record("r-1", "search", {"token": "ghp_" + "c" * 36})
    audit.record("r-2", "merge", {"path": "C:\\Users\\bob\\x"})
    result = get_diagnostics({"id": "r-1"}, b"", "")
    assert result["event_count"] == 1
    assert "ghp_" not in str(result)


def test_unknown_request_id_404():
    with pytest.raises(DomainError) as error:
        get_diagnostics({"id": "missing"}, b"", "")
    assert error.value.code == "E_NOT_FOUND"


def test_oversized_export_is_truncated():
    for index in range(1200):
        audit.record("big", "event", {"blob": "x" * 5000})
    result = get_diagnostics({"id": "big"}, b"", "")
    assert result["truncated"] is True
    assert result["event_count"] <= 1000
    assert result["bytes"] <= MAX_BYTES