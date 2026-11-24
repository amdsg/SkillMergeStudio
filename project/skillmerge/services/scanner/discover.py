from __future__ import annotations

import os
from typing import Dict, Iterable, List, Optional, Tuple

from ...config import defaults


def _candidate_roots(home: str, appdata: str, localappdata: str, project: str) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
    for entry in defaults.PROBE_PLATFORMS:
        platform = str(entry["platform"])
        for relative in entry["paths"]:
            items.append((os.path.join(home, relative.replace("/", os.sep)), platform))
            name = str(relative).replace("/", os.sep)
            if appdata:
                items.append((os.path.join(appdata, name), platform))
            if localappdata:
                items.append((os.path.join(localappdata, name), platform))
    for relative in (".claude", ".cursor", ".agents", ".codex", ".github/copilot"):
        items.append((os.path.join(project, relative.replace("/", os.sep)), "project"))
    return items


def detect_roots(
    home: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    extra_roots: Iterable[str] = (),
    include_missing: bool = False,
) -> List[Dict[str, str]]:
    source = env if env is not None else os.environ
    home_dir = os.path.expanduser(home or source.get("USERPROFILE") or source.get("HOME") or "~")
    appdata = source.get("APPDATA", "")
    localappdata = source.get("LOCALAPPDATA", "")
    project = os.getcwd()
    seen = set()
    result: List[Dict[str, str]] = []
    for path, platform in _candidate_roots(home_dir, appdata, localappdata, project):
        normalized = os.path.normcase(os.path.abspath(path))
        if normalized in seen:
            continue
        seen.add(normalized)
        exists = os.path.isdir(path)
        if exists or include_missing:
            result.append({"path": os.path.normpath(path), "platform": platform, "exists": exists})
    for extra in extra_roots:
        expanded = os.path.abspath(os.path.expanduser(str(extra)))
        normalized = os.path.normcase(expanded)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isdir(expanded):
            result.append({"path": expanded, "platform": "custom", "exists": True})
    return result


def platform_for_path(path: str, roots: Iterable[Dict[str, str]]) -> str:
    best = "unknown"
    best_length = -1
    target = os.path.normcase(os.path.abspath(path))
    for item in roots:
        root = os.path.normcase(os.path.abspath(item["path"]))
        if target == root or target.startswith(root + os.sep):
            if len(root) > best_length:
                best = str(item.get("platform", "unknown"))
                best_length = len(root)
    return best


def existing_root_paths(roots: Iterable[Dict[str, str]]) -> List[str]:
    return [item["path"] for item in roots if item.get("exists")]