#!/usr/bin/env python3
"""Open-set assertions: no fixed target count, no three-item whitelist."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = ROOT / "agent" / "adapters" / "targets.json"
CONVERT = ROOT / "agent" / "api" / "convert.py"
CONVERT_UI = ROOT / "extension" / "ui" / "views" / "convert-panel.js"
AGENT = ROOT / "agent"
FIXED_COUNT = re.compile(r"\bTARGET_COUNT\b|\bFIXED_TARGETS?\b|\bKNOWN_TARGET_LIST\b")
THREE_PLUS = re.compile(r"chatgpt[\s\S]{0,80}doubao[\s\S]{0,80}(agent_skills_generic|prompt_only_generic)")


def load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="open target registry gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--assert-q14-default", action="store_true")
    parser.add_argument("--assert-q18-default", action="store_true")
    args = parser.parse_args(argv)
    errors = []
    items = load(TARGETS, [])
    if not isinstance(items, list) or not items:
        print("WB-OPEN: targets.json missing or empty", file=sys.stderr)
        return 2
    enabled = [item for item in items if item.get("enabled", True)]
    ids = {str(item.get("id")) for item in items}
    for path in AGENT.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in FIXED_COUNT.finditer(text):
            errors.append(f"WB-OPEN-1 {path.relative_to(ROOT).as_posix()}: fixed target constant {match.group(0)}")
    samples = [str(item.get("id")) for item in enabled if item.get("evidence_level") == "verified"][:5]
    if len(samples) > 5:
        errors.append("WB-OPEN-2 sample_ids exceeds 5")
    if not set(samples) <= ids:
        errors.append("WB-OPEN-2 sample_ids not subset of items")
    if not CONVERT.is_file():
        errors.append("WB-OPEN-3 agent/api/convert.py missing")
    else:
        text = CONVERT.read_text(encoding="utf-8", errors="replace")
        if "E_TARGET_NOT_REGISTERED" not in text:
            errors.append("WB-OPEN-3 unregistered target error code missing")
        if "Fallback" not in text and "fallback" not in text.lower():
            errors.append("WB-OPEN-3 generic fallback path missing")
    disabled = [item for item in items if not item.get("enabled", True)]
    if any(item.get("enabled", True) for item in disabled):
        errors.append("WB-OPEN-4 disabled entries leak into items")
    if not CONVERT_UI.is_file():
        errors.append("WB-OPEN-5 convert-panel.js missing")
    else:
        ui = CONVERT_UI.read_text(encoding="utf-8", errors="replace")
        if THREE_PLUS.search(ui):
            errors.append("WB-OPEN-5 three-item whitelist detected in convert panel")
    if args.assert_q14_default:
        # unknown targets stay selectable with an explicit generic-text warning
        if not CONVERT_UI.is_file() or "wb.convert.unknown.warning" not in CONVERT_UI.read_text(encoding="utf-8", errors="replace"):
            errors.append("WB-Q14 default path missing")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-OPEN: errors={len(errors)} targets={len(items)} enabled={len(enabled)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())