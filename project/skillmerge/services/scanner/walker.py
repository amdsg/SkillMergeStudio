from __future__ import annotations

import os
import time
import fnmatch
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from ...config import defaults
from .stats import ScanAccumulator

SYSTEM_DIRS = frozenset(
    {"Windows", "$Recycle.Bin", "System Volume Information", "Recovery", "PerfLogs", "ProgramData"}
)
SKILL_FILE = "SKILL.md"


@dataclass
class WalkOptions:
    depth: int = defaults.DEFAULT_SCAN_DEPTH
    limit: int = defaults.DEFAULT_SCAN_LIMIT
    time_limit: int = defaults.DEFAULT_SCAN_TIME_LIMIT
    prune_names: Iterable[str] = defaults.PRUNE_NAMES
    ignore_rules: Iterable[str] = ()
    cancel_check_every: int = defaults.CANCEL_CHECK_EVERY


@dataclass
class WalkResult:
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    accumulator: ScanAccumulator = field(default_factory=ScanAccumulator)
    cancelled: bool = False
    roots: List[str] = field(default_factory=list)


def _matches_ignore(rel_path: str, name: str, rules: Iterable[str]) -> bool:
    for rule in rules:
        pattern = str(rule)
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True
        if pattern.startswith("**/") and fnmatch.fnmatch(name, pattern[3:]):
            return True
    return False


def _root_platform(path: str, roots: List[Dict[str, str]]) -> str:
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


def _list_entries(path: str, acc: ScanAccumulator) -> Optional[List[Any]]:
    try:
        entries = list(os.scandir(path))
    except PermissionError as exc:
        acc.permission_error(path, f"无权限：{exc}")
        return None
    except OSError as exc:
        acc.permission_error(path, f"无法访问：{exc}")
        return None
    entries.sort(key=lambda entry: entry.name.lower())
    return entries


def _scan_entries(
    entries: List[Any],
    path: str,
    depth: int,
    platform: str,
    stack: List[Tuple[str, int, str]],
    result: WalkResult,
    opts: WalkOptions,
    roots: List[Dict[str, str]],
    cancel_token: Any,
) -> Optional[str]:
    acc = result.accumulator
    for entry in entries:
        if cancel_token is not None and getattr(cancel_token, "is_cancelled", lambda: False)():
            return "cancelled"
        try:
            if entry.is_symlink():
                continue
            if entry.is_dir(follow_symlinks=False):
                name = entry.name
                if name in SYSTEM_DIRS or name in opts.prune_names:
                    acc.pruned(name)
                    continue
                if _matches_ignore(os.path.join(path, name), name, opts.ignore_rules):
                    acc.pruned(name)
                    continue
                if depth + 1 > opts.depth:
                    acc.pruned("MAX_DEPTH")
                    continue
                stack.append((entry.path, depth + 1, _root_platform(entry.path, roots) or platform))
                continue
            if entry.name != SKILL_FILE or not entry.is_file(follow_symlinks=False):
                continue
            stat = entry.stat(follow_symlinks=False)
        except OSError as exc:
            acc.permission_error(entry.path, f"读取失败：{exc}")
            continue
        if len(result.candidates) >= opts.limit:
            remaining = [item[0] for item in stack] + [entry.path]
            acc.limit_reached(remaining)
            stack.clear()
            return "limit"
        acc.found()
        result.candidates.append(
            {
                "path": os.path.normpath(entry.path),
                "root": path,
                "platform": _root_platform(entry.path, roots) or platform,
                "mtime": float(stat.st_mtime),
                "size": int(stat.st_size),
            }
        )
    return None


def walk(
    roots: List[Dict[str, str]],
    options: WalkOptions = None,
    cancel_token: Any = None,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> WalkResult:
    opts = options or WalkOptions()
    result = WalkResult(roots=[item["path"] for item in roots])
    acc = result.accumulator
    stack: List[Tuple[str, int, str]] = [
        (item["path"], 0, str(item.get("platform", "unknown"))) for item in roots
    ]
    started = time.monotonic()
    visited = 0
    while stack:
        if cancel_token is not None and getattr(cancel_token, "is_set", None) and cancel_token.is_set():
            result.cancelled = True
            break
        if visited % max(1, opts.cancel_check_every) == 0:
            if time.monotonic() - started >= opts.time_limit:
                acc.time_reached()
                break
            if progress:
                progress(visited, 0, f"已扫描 {visited} 个目录")
        path, depth, platform = stack.pop()
        visited += 1
        entries = _list_entries(path, acc)
        if entries is None:
            continue
        outcome = _scan_entries(entries, path, depth, platform, stack, result, opts, roots, cancel_token)
        if outcome == "cancelled":
            result.cancelled = True
            break
        if outcome == "limit":
            break
    if progress:
        progress(visited, 0, f"扫描结束，发现 {len(result.candidates)} 个候选")
    return result


def walk_roots(
    roots: List[str],
    platform_map: Optional[List[Dict[str, str]]] = None,
    options: WalkOptions = None,
    cancel_token: Any = None,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> WalkResult:
    mapping = platform_map or [{"path": root, "platform": "unknown"} for root in roots]
    return walk(mapping, options, cancel_token, progress)