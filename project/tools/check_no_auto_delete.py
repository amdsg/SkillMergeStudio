#!/usr/bin/env python3
"""N-01~N-07：禁止 `.trash` 自动删除的静态门禁。"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DELETE_CALLS = {"rmtree", "unlink", "remove", "replace", "rename", "move"}
BAD_TEXT = re.compile(r"自动清理|到期删除|auto\s*purge|auto\s*cleanup", re.I)
NEGATION = re.compile(r"禁止|不得|未|不|无法|没有")
AUTO_CONFIG = re.compile(r"auto_cleanup|auto_purge|trash\.auto", re.I)


def _call_name(node) -> str:
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute):
            return func.attr
        if isinstance(func, ast.Name):
            return func.id
    return ""


def _scan_python(path: Path, issues: list) -> None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return
    if path.name == "fsops.py":
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            text = ast.unparse(node).lower()
            if name in DELETE_CALLS and ".trash" in text:
                issues.append(f"N-01 {path}:{node.lineno}: {name} on .trash")
            if name in ("Timer", "call_later") and "trash" in text:
                issues.append(f"N-03 {path}:{node.lineno}: background scheduler")
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            body = ast.unparse(node).lower()
            if "trash" in body and any(call in body for call in DELETE_CALLS):
                issues.append(f"N-03 {path}:{node.lineno}: while True cleanup")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lowered = node.name.lower()
            if any(key in lowered for key in ("cleanup", "purge_all", "expire", "gc")):
                body = ast.unparse(node).lower()
                if "trash" in body and any(f".{call}(" in body for call in DELETE_CALLS):
                    issues.append(f"N-02 {path}:{node.lineno}: function {node.name}")


def _scan_text(path: Path, issues: list) -> None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    rel = path.as_posix()
    for number, line in enumerate(lines, 1):
        if BAD_TEXT.search(line) and not NEGATION.search(line):
            issues.append(f"N-05 {rel}:{number}: 自动删除表述")
        if AUTO_CONFIG.search(line):
            issues.append(f"N-04 {rel}:{number}: 自动清理配置键")


def scan(root: Path) -> list:
    issues = []
    for path in sorted((root / "skillmerge").rglob("*.py")) if (root / "skillmerge").is_dir() else []:
        _scan_python(path, issues)
    for path in sorted((root / "config").rglob("*.py")) if (root / "config").is_dir() else []:
        _scan_text(path, issues)
    web = root / "web"
    if web.is_dir():
        for path in sorted(web.rglob("*.js")):
            _scan_text(path, issues)
        html = web / "index.html"
        if html.is_file():
            _scan_text(html, issues)
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="禁止 .trash 自动删除")
    parser.add_argument("--root", default="")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else ROOT
    issues = scan(root)
    for issue in issues:
        print(issue, file=sys.stderr)
    print(f"N-01~N-07: issues={len(issues)} root={root}")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())