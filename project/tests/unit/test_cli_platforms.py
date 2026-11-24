from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def test_cli_platforms_json_contract():
    result = subprocess.run(
        [sys.executable, "-m", "skillmerge", "platforms", "--json"],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["ok"] is True
    data = payload["data"]
    assert data["counts"]["total"] == 28
    assert data["counts"]["verified"] == 3
    assert data["page"]["total"] == 28
    assert data["items"]
    assert not [item for item in data["diagnostics"] if item["severity"] == "error"]
    assert "counts=" in result.stderr


def test_cli_platforms_invalid_filter_exit_two():
    result = subprocess.run(
        [sys.executable, "-m", "skillmerge", "platforms", "--kind", "plugin", "--json"],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout.splitlines()[0])
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"