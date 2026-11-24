from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(ROOT, "tests", "fixtures")
SKILLS = os.path.join(FIXTURES, "skills")
ENV = dict(os.environ, PYTHONIOENCODING="utf-8")


def test_cli_scan_outputs_single_json(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "skillmerge", "scan", "--root", SKILLS, "--json", "--data-dir", str(tmp_path / "data")],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["ok"] is True
    assert payload["data"]["stats"]["found"] >= 4
    assert result.stderr


def test_cli_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "skillmerge", "--help"],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0
    assert "scan" in result.stdout


def test_server_help_exits_zero():
    result = subprocess.run(
        [sys.executable, "server.py", "--help"],
        cwd=ROOT,
        env=ENV,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0
    assert "--port" in result.stdout