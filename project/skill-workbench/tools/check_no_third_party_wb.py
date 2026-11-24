#!/usr/bin/env python3
"""Zero third-party runtime dependencies, no build chain, no remote code."""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENT = ROOT / "agent"
REMOTE_CODE = re.compile(r"(?:src|import)\s*[=(]\s*['\"]https?://", re.I)
EVAL = re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(")
FORBIDDEN_ARTIFACTS = ("node_modules", "package-lock.json", "yarn.lock", "webpack.config.js", "vite.config.js")


def stdlib_names() -> set[str]:
    names = set(sys.stdlib_module_names)
    names.update({"__future__", "agent"})
    return names


def imported_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="zero-dependency gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", default="")
    args = parser.parse_args(argv)
    scan_root = Path(args.root) if args.root else ROOT
    if not scan_root.is_absolute():
        scan_root = (ROOT.parent / scan_root).resolve()
    errors = []
    allowed = stdlib_names()
    for path in AGENT.rglob("*.py"):
        for name in imported_names(path):
            if name not in allowed:
                errors.append(f"WB-DEP-1 {path.relative_to(scan_root).as_posix()}: third-party import {name}")
    for name in FORBIDDEN_ARTIFACTS:
        for path in scan_root.rglob(name):
            errors.append(f"WB-DEP-2 build artifact {path.relative_to(scan_root).as_posix()}")
    for path in scan_root.rglob("*.js"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if REMOTE_CODE.search(text):
            errors.append(f"WB-DEP-3 {path.relative_to(scan_root).as_posix()}: remote script/import")
        if EVAL.search(text):
            errors.append(f"WB-DEP-4 {path.relative_to(scan_root).as_posix()}: eval/new Function")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-DEP: errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())