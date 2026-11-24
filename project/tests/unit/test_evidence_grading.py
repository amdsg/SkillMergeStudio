from __future__ import annotations

import json
import os
import subprocess
import sys

from skillmerge.services.exporter.platform_registry.discovery_reader import grade

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DISCOVERY = os.path.join(ROOT, "platforms", "discovery", "2026-11-22.json")


def record(status=200, markers=None, kind_key="x"):
    return {
        "key": kind_key,
        "label": kind_key,
        "url": "https://example.com/" + kind_key,
        "final_url": "https://example.com/" + kind_key,
        "status": status,
        "error": "" if status else "timeout",
        "title": kind_key,
        "bytes_read": 100 if status == 200 else 0,
        "markers": markers or {},
    }


def test_grade_boundaries_never_verified():
    assert grade(record(markers={"skill_md": True}), ()) == "candidate_skill"
    assert grade(record(markers={"rules_word": True}), ()) == "candidate_rules"
    assert grade(record(markers={"agent_skills": True}), ()) == "candidate_rules"
    assert grade(record(markers={}), ()) == "no_evidence"
    assert grade(record(status=404), ()) == "failed_unreachable"
    assert grade(record(status=None), ()) == "failed_unreachable"
    assert grade(record(markers={"skill_md": True}), ("x",)) == "discovery_source"
    assert grade(record(markers={"skill_md": True}), ()) != "verified"


def test_grade_tool_writes_and_checks_summary(tmp_path):
    source = str(tmp_path / "2026-11-22.json")
    with open(DISCOVERY, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    with open(source, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    with open(str(tmp_path / "2026-11-22.meta.json"), "w", encoding="utf-8") as handle:
        json.dump({"discovery_keys": ["skills-sh"]}, handle)
    write = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "grade_evidence.py"), "--file", source, "--write"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert write.returncode == 0, write.stderr
    summary_path = os.path.join(str(tmp_path), "summary-2026-11-22.json")
    assert os.path.isfile(summary_path)
    summary = json.load(open(summary_path, encoding="utf-8"))
    assert summary["skill_md"] == 14
    assert summary["rules"] == 21
    check = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "grade_evidence.py"), "--file", source, "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert check.returncode == 0, check.stderr
    summary["rules"] = 22
    with open(summary_path, "w", encoding="utf-8") as handle:
        json.dump(summary, handle)
    check_again = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "grade_evidence.py"), "--file", source, "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    assert check_again.returncode == 1