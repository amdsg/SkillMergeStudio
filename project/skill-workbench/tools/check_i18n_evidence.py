#!/usr/bin/env python3
"""15-screen evidence matrix: reports blocked states, never creates evidence."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WB = Path(__file__).resolve().parent.parent
SCREENS = WB / "extension" / "i18n-screens.json"
EVIDENCE = WB / "docs" / "i18n-evidence"
SUFFIXES = (".png", ".jpg", ".jpeg", ".html", ".txt")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="i18n evidence matrix gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(SCREENS.read_text(encoding="utf-8"))
    screens = data.get("screens") or []
    files = [path for path in EVIDENCE.rglob("*") if path.is_file() and path.suffix.lower() in SUFFIXES] if EVIDENCE.is_dir() else []
    rows = []
    covered = 0
    for screen in screens:
        screen_id = screen.get("screen_id", "")
        for state in screen.get("states") or []:
            matched = [path for path in files if screen_id in path.name and state in path.name]
            status = "covered" if matched else "blocked"
            if matched:
                covered += 1
            rows.append({"screen_id": screen_id, "state": state, "status": status, "file": matched[0].name if matched else ""})
    total = len(rows)
    blocked = total - covered
    payload = {"total": total, "covered": covered, "blocked": blocked, "evidence_dir": str(EVIDENCE), "rows": rows}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=1))
    else:
        print(f"WB-I18N-EVIDENCE: total={total} covered={covered} blocked={blocked}")
        for row in rows:
            if row["status"] != "covered":
                print(f"BLOCKED {row['screen_id']}__{row['state']}")
    return 0 if blocked == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())