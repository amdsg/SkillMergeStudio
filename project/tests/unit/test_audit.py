from __future__ import annotations

import pytest

from skillmerge.util.audit import ACTIONS, read_audit, write_audit


def test_write_and_read_roundtrip(tmp_path):
    data_dir = str(tmp_path)
    for action in ACTIONS:
        assert write_audit(data_dir, action, f"target-{action}", "ok")
    rows = read_audit(data_dir, 10)
    assert len(rows) == len(ACTIONS)
    assert rows[0]["action"] == ACTIONS[-1]
    assert all(row["operator"] == "local" for row in rows)
    assert all(row["at"] for row in rows)


def test_invalid_action_rejected(tmp_path):
    with pytest.raises(ValueError):
        write_audit(str(tmp_path), "unknown", "x", "ok")


def test_secret_is_redacted(tmp_path):
    data_dir = str(tmp_path)
    write_audit(data_dir, "config", "config.json", "ok", {"api_key": "sk-test-secret-123456"})
    text = (tmp_path / "audit.log").read_text(encoding="utf-8")
    assert "sk-test-secret-123456" not in text
    assert "***" in text


def test_missing_log_returns_empty(tmp_path):
    assert read_audit(str(tmp_path / "nope"), 5) == []