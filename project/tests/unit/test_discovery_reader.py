from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from skillmerge.services.exporter.platform_registry.discovery_reader import grade, load_round

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DISCOVERY = os.path.join(ROOT, "platforms", "discovery", "2026-11-22.json")


def test_actual_discovery_counts():
    result = load_round(DISCOVERY)
    assert result is not None
    summary = result.summary
    assert summary["probed"] == 77
    assert summary["ok"] == 49
    assert summary["failed"] == 28
    assert summary["skill_md"] == 14
    assert summary["rules"] == 21
    assert summary["discovery"] == 1
    assert summary["no_evidence"] == 13
    assert all(summary["equations"].values())
    assert not [item for item in result.issues if item["severity"] == "error"]
    assert grade(next(record for record in result.records if record["key"] == "claude-skills"), ("skills-sh",)) == "candidate_skill"
    assert all(grade(record, ("skills-sh",)) != "verified" for record in result.records)


def test_missing_meta_rolls_discovery_source_to_rules(tmp_path):
    path = str(tmp_path / "2026-11-22.json")
    shutil.copyfile(DISCOVERY, path)
    result = load_round(path)
    assert result.summary["rules"] == 22
    assert result.summary["discovery"] == 0
    assert "KIND_MISSING" in {item["code"] for item in result.issues}


def test_duplicate_url_and_corrupt_record(tmp_path):
    path = str(tmp_path / "probe.json")
    payload = {
        "generated_at": "2026-11-22",
        "candidates": [
            {"key": "a", "label": "A", "url": "https://example.com/a", "final_url": "https://example.com/a",
             "status": 200, "error": "", "title": "A", "bytes_read": 10, "markers": {"skill_md": True}},
            {"key": "b", "label": "B", "url": "https://example.com/a", "final_url": "https://example.com/a",
             "status": 200, "error": "", "title": "B", "bytes_read": 10, "markers": {"skill_md": False}},
            {"key": "c", "label": "C", "url": "https://example.com/c", "final_url": "https://example.com/c"},
        ],
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    result = load_round(path)
    codes = {item["code"] for item in result.issues}
    assert "DISCOVERY_DUPLICATE_URL" in codes
    assert "DISCOVERY_NO_RESULT" in codes
    corrupt = str(tmp_path / "corrupt.json")
    with open(corrupt, "w", encoding="utf-8") as handle:
        handle.write("{bad")
    assert any(item["code"] == "DISCOVERY_CORRUPT" for item in load_round(corrupt).issues)


def test_validate_discovery_cli_reports_summary():
    result = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "validate_discovery.py"), DISCOVERY],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["skill_md"] == 14
    assert payload["summary"]["rules"] == 21