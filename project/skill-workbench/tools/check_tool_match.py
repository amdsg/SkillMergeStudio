#!/usr/bin/env python3
"""Tool matching gate: no fuzzy matching, detected-state only, four reason codes."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOL_MATCH = ROOT / "agent" / "core" / "tool_match.py"
AGENT = ROOT / "agent"
REASONS = {
    "matched_detected",
    "no_tool_hint",
    "no_detected_tool",
    "tool_evidence_unknown",
}
FUZZY = ("difflib", "SequenceMatcher", "get_close_matches")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="tool matching gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--cases", default="")
    args = parser.parse_args(argv)
    errors = []
    for path in AGENT.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in FUZZY:
            if token in text:
                errors.append(f"WB-TOOL-1 {path.relative_to(ROOT).as_posix()}: fuzzy matcher {token}")
    if not TOOL_MATCH.is_file():
        errors.append("WB-TOOL-2 agent/core/tool_match.py missing")
    else:
        text = TOOL_MATCH.read_text(encoding="utf-8", errors="replace")
        for reason in sorted(REASONS):
            if reason not in text:
                errors.append(f"WB-TOOL-2 missing reason_code {reason}")
        if "detected" not in text:
            errors.append("WB-TOOL-2 recommended tool must only come from detected state")
    cases_dir = Path(args.cases) if args.cases else ROOT / "tests_wb" / "fixtures" / "tool-match"
    case_file = cases_dir / "cases.json"
    if case_file.is_file():
        data = json.loads(case_file.read_text(encoding="utf-8"))
        for case in data if isinstance(data, list) else []:
            if case.get("expect_null") and case.get("similar_name") and not case.get("hints"):
                if case.get("actual") is not None:
                    errors.append(f"WB-TOOL-3 {case.get('id')}: similar name must not match")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-TOOL: errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())