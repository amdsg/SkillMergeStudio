from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)\s*(.*)$")
_OPERATORS = ("===", "==", ">=", "<=", "~=", "!=", ">", "<")


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", (name or "").strip().lower())


def _split(entry: Dict[str, Any]) -> tuple:
    raw = str(entry.get("raw") or entry.get("name") or "").strip()
    value = str(entry.get("name") or raw).strip()
    match = _NAME_RE.match(value)
    if not match:
        return normalize_name(value), value, ""
    name, rest = match.group(1), match.group(2).strip()
    if not rest:
        for operator in _OPERATORS:
            if operator in raw:
                rest = raw[raw.find(operator):].strip()
                break
    return normalize_name(name), name, rest


def _strictness(spec: str) -> int:
    if spec.startswith("==="):
        return 6
    if spec.startswith("=="):
        return 5
    if spec.startswith(">="):
        return 4
    if spec.startswith(">"):
        return 3
    if spec.startswith("~="):
        return 2
    if spec.startswith("<="):
        return 1
    if spec.startswith("<"):
        return 1
    return 0


def aggregate(dependencies: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    buckets: Dict[str, Dict[str, Any]] = {}
    for entry in dependencies:
        key, name, spec = _split(entry)
        if not key:
            continue
        bucket = buckets.setdefault(key, {"key": key, "name": name, "specs": set()})
        if spec:
            bucket["specs"].add(spec)
    result = []
    for key in sorted(buckets):
        bucket = buckets[key]
        specs = sorted(bucket["specs"], key=lambda item: (_strictness(item), item), reverse=True)
        result.append({"name": bucket["name"], "spec": specs[0] if specs else "", "key": key})
    return result


def install_command(packages: List[Dict[str, str]]) -> str:
    parts = []
    for package in packages:
        spec = package.get("spec", "")
        if spec:
            parts.append(f'"{package["name"]}{spec}"')
        else:
            parts.append(package["name"])
    return "python -m pip install " + " ".join(parts) if parts else ""


def environment_section(packages: List[Dict[str, str]]) -> str:
    if not packages:
        return ""
    lines = ["## 环境要求", ""]
    for package in packages:
        spec = package.get("spec", "")
        lines.append(f'- `{package["name"]}`' + (f"（{spec}）" if spec else ""))
    lines.extend(["", "```bash", install_command(packages), "```", ""])
    return "\n".join(lines)