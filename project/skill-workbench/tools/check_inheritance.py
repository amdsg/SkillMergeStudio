#!/usr/bin/env python3
"""Inheritance gate: upstream spec missing -> blocked, never claim 189 inherited."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WB_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = WB_ROOT.parent
INHERITANCE = WB_ROOT / "agent" / "store" / "records" / "inheritance.json"
FORBIDDEN = (
    re.compile(r"已继承\s*189\s*条"),
    re.compile(r"已复用全部能力"),
    re.compile(r"inherited\s+all\s+189", re.I),
)
NEGATION = re.compile(r"不得|禁止|未|不|无法|不可|没有|cannot|not", re.I)


def load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def scan(paths):
    issues = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for pattern in FORBIDDEN:
                for match in pattern.finditer(line):
                    window = line[max(0, match.start() - 14): match.end() + 14]
                    if NEGATION.search(window):
                        continue
                    issues.append(f"WB-INH-2 {path.relative_to(PROJECT_ROOT).as_posix()}:{number}: {match.group(0)}")
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="inheritance gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--scan-root", default="")
    parser.add_argument("--report", default="")
    args = parser.parse_args(argv)
    errors = []
    data = load(INHERITANCE, None)
    if not isinstance(data, dict):
        errors.append("WB-INH-1 inheritance.json missing")
        data = {}
    state = str(data.get("state", ""))
    reason = str(data.get("reason_code", ""))
    if state != "blocked":
        errors.append(f"WB-INH-1 expected blocked actual {state or '<empty>'}")
    if reason != "inheritance_source_missing":
        errors.append(f"WB-INH-1 expected inheritance_source_missing actual {reason or '<empty>'}")
    if not data.get("path") or not data.get("checked_at"):
        errors.append("WB-INH-1 blocked record must include path and checked_at")
    scan_root = Path(args.scan_root) if args.scan_root else PROJECT_ROOT
    if not scan_root.is_absolute():
        scan_root = (PROJECT_ROOT / scan_root).resolve()
    candidates = list(WB_ROOT.rglob("*"))
    docs = scan_root / "docs"
    if docs.is_dir():
        candidates += list(docs.rglob("*"))
    readme = scan_root / "README.txt"
    if readme.is_file():
        candidates.append(readme)
    def _is_gate_source(path: Path) -> bool:
        try:
            parts = path.relative_to(WB_ROOT).parts
        except ValueError:
            return False
        return bool(parts) and parts[0] == "tools"

    files = [
        path for path in candidates
        if path.is_file()
        and path.suffix in {".md", ".txt", ".js", ".json", ".py"}
        and not _is_gate_source(path)
    ]
    errors.extend(scan(files))
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"state": state, "reason_code": reason, "errors": errors}, ensure_ascii=False, indent=1), encoding="utf-8")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-INH: state={state or '<empty>'} blocked_not_counted=true errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())