#!/usr/bin/env python3
"""Tutorial gate: the tutorial must not perform any write or agent request."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TUTORIAL = ROOT / "extension" / "ui" / "views" / "tutorial-overlay.js"
FORBIDDEN = (
    (re.compile(r"\bfetch\s*\("), "fetch"),
    (re.compile(r"\bagentClient\s*\."), "agentClient"),
    (re.compile(r"agent-client\.js"), "agent-client import"),
    (re.compile(r"/install/apply|/upgrade/apply|/convert\b"), "write endpoint"),
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="tutorial no-write gate")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    errors = []
    if not TUTORIAL.is_file():
        errors.append("WB-TUT-1 tutorial-overlay.js missing")
    else:
        text = TUTORIAL.read_text(encoding="utf-8", errors="replace")
        for pattern, label in FORBIDDEN:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"WB-TUT-1 tutorial-overlay.js:{line}: {label}")
        if "ui.focusTarget" not in text:
            errors.append("WB-TUT-2 focusTarget event missing")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-TUT: errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())