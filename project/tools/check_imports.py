from __future__ import annotations

import ast
import os
import sys

ALLOWED = {
    "app": {"app", "http", "api", "services", "storage", "config", "security", "jobs", "util"},
    "http": {"http", "api", "security", "util"},
    "api": {"api", "services", "storage", "config", "util"},
    "services": {"services", "storage", "security", "config", "util"},
    "storage": {"storage", "util"},
    "config": {"config", "util"},
    "jobs": {"jobs", "storage", "util"},
    "cli": {"cli", "services", "config", "storage", "util", "app"},
    "security": {"security", "util"},
    "util": {"util"},
}


def _module_for(path: str) -> str:
    relative = os.path.relpath(path, os.getcwd()).replace(os.sep, "/")
    if relative == "server.py":
        return "server"
    if relative.startswith("skillmerge/"):
        relative = relative[len("skillmerge/"):]
        if relative.endswith("/__init__.py"):
            relative = relative[: -len("/__init__.py")]
        elif relative.endswith(".py"):
            relative = relative[:-3]
        return "skillmerge." + relative.replace("/", ".")
    return relative.replace("/", ".").replace(".py", "")


def _layer(module: str) -> str:
    if module == "server":
        return "app"
    if module == "skillmerge.__main__":
        return "cli"
    parts = module.split(".")
    if len(parts) < 2:
        return "util"
    name = parts[1]
    if name in ("scanner", "parser", "classifier", "merger", "exporter", "history"):
        return "services"
    if name in ALLOWED:
        return name
    return "util"


def _imports(path: str, module: str) -> list:
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        tree = ast.parse(handle.read(), filename=path)
    result = []
    package = module.rsplit(".", 1)[0] if "." in module else ""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("skillmerge"):
                    result.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base_parts = package.split(".")
                if node.level > 1:
                    base_parts = base_parts[:-(node.level - 1)]
                base = ".".join(base_parts)
                target = base + ("." + node.module if node.module else "")
            else:
                target = node.module or ""
            if target.startswith("skillmerge"):
                result.append(target)

    return result


def _module_exists(target: str) -> bool:
    path = target.replace(".", os.sep)
    return os.path.isfile(path + ".py") or os.path.isfile(os.path.join(path, "__init__.py"))


NETWORK_MODULES = ("urllib.request", "urllib.error", "http.client", "requests", "aiohttp", "httpx", "socket")

NET_EXEMPT = {
    os.path.normpath(os.path.join("skillmerge", "services", "ai_client.py")),
}


def _forbidden_net() -> int:
    issues = []
    exempted = []
    for base in ("skillmerge/services", "skillmerge/api"):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [name for name in dirnames if name != "__pycache__"]
            for name in sorted(filenames):
                if not name.endswith(".py"):
                    continue
                path = os.path.join(dirpath, name)
                if os.path.normpath(path) in NET_EXEMPT:
                    exempted.append(path)
                    continue
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith(NETWORK_MODULES):
                                issues.append(f"{path}: 禁止运行时代码 import {alias.name}")
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        if node.module.startswith(NETWORK_MODULES):
                            issues.append(f"{path}: 禁止运行时代码 import {node.module}")
    if issues:
        print("网络依赖门禁失败：", file=sys.stderr)
        for issue in issues:
            print(" - " + issue, file=sys.stderr)
        return 1
    for path in exempted:
        print(f"网络依赖门禁豁免：{path}（设计 A-16 唯一出站模块，默认关闭）", file=sys.stderr)
    print("网络依赖门禁通过（services/api 无出站网络 import）", file=sys.stderr)
    return 0


def main() -> int:
    if "--forbidden-net" in sys.argv[1:]:
        return _forbidden_net()
    issues = []
    graph = {}
    files = []
    for dirpath, dirnames, filenames in os.walk("skillmerge"):
        dirnames[:] = [name for name in dirnames if name != "__pycache__"]
        for name in sorted(filenames):
            if name.endswith(".py"):
                files.append(os.path.join(dirpath, name))
    if os.path.isfile("server.py"):
        files.append("server.py")
    for path in files:
        module = _module_for(path)
        layer = _layer(module)
        targets = []
        for target in _imports(path, module):
            target_layer = _layer(target)
            if target_layer == layer:
                continue
            if target_layer not in ALLOWED.get(layer, {layer}):
                issues.append(f"{path}: {layer} 不允许依赖 {target_layer}（{target}）")
            targets.append(target)
        graph[module] = [item for item in targets if _module_exists(item)]

    visited = {}
    stack = []

    def visit(node):
        state = visited.get(node, 0)
        if state == 1:
            cycle = " -> ".join(stack[stack.index(node):] + [node])
            issues.append(f"循环导入：{cycle}")
            return
        if state == 2:
            return
        visited[node] = 1
        stack.append(node)
        for child in graph.get(node, []):
            if child in graph:
                visit(child)
        stack.pop()
        visited[node] = 2

    for node in sorted(graph):
        visit(node)
    if issues:
        print("依赖检查失败：", file=sys.stderr)
        for issue in issues:
            print(" - " + issue, file=sys.stderr)
        return 1
    print(f"依赖检查通过（{len(graph)} 个模块）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())