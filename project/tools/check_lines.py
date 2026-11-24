from __future__ import annotations

import ast
import os
import sys

MAX_FILE_LINES = 600
MAX_FUNCTION_LINES = 60
ROOTS = ("skillmerge", "server.py", "tools", "web")
EXTENSIONS = (".py", ".js", ".css", ".html")


def _files() -> list:
    result = []
    for root in ROOTS:
        if os.path.isfile(root):
            result.append(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in ("__pycache__", ".git")]
            for name in sorted(filenames):
                if name.endswith(EXTENSIONS):
                    result.append(os.path.join(dirpath, name))
    return result


def check_file(path: str) -> list:
    issues = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        source = handle.read()
    lines = source.count("\n") + (0 if source.endswith("\n") else 1)
    if lines > MAX_FILE_LINES:
        issues.append(f"{path}: 文件 {lines} 行，超过 {MAX_FILE_LINES}")
    if not path.endswith(".py"):
        return issues
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        issues.append(f"{path}: 语法错误 {exc}")
        return issues
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = getattr(node, "end_lineno", node.lineno)
            size = end - node.lineno + 1
            if size > MAX_FUNCTION_LINES:
                issues.append(f"{path}:{node.lineno} 函数 {node.name} 有 {size} 行，超过 {MAX_FUNCTION_LINES}")
    return issues


def main() -> int:
    issues = []
    for path in _files():
        issues.extend(check_file(path))
    if issues:
        print("行数检查失败：", file=sys.stderr)
        for issue in issues:
            print(" - " + issue, file=sys.stderr)
        return 1
    print(f"行数检查通过（{len(_files())} 个文件）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())