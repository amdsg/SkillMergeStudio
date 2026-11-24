from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

MAX_ITEMS = 2000
MAX_WALK_ENTRIES = 50000


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(float(timestamp), timezone.utc).isoformat()


def _walk_bytes(path: str, budget: int) -> Tuple[int, int, bool, bool]:
    total = 0
    entries = 0
    unreadable = False
    for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
        dirnames[:] = [name for name in dirnames if not os.path.islink(os.path.join(dirpath, name))]
        for name in filenames:
            if entries >= budget:
                return total, entries, unreadable, True
            entries += 1
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                unreadable = True
                continue
            try:
                total += os.path.getsize(full)
            except OSError:
                unreadable = True
    return total, entries, unreadable, False


def _collect(root: str):
    items = []
    total_bytes = 0
    unreadable = 0
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return items, total_bytes, unreadable, False
    budget = MAX_WALK_ENTRIES
    truncated = len(names) > MAX_ITEMS
    for name in names[:MAX_ITEMS]:
        full = os.path.join(root, name)
        try:
            info = os.lstat(full)
        except FileNotFoundError:
            continue
        except OSError:
            unreadable += 1
            continue
        is_link = os.path.islink(full)
        is_dir = os.path.isdir(full) and not is_link
        size = 0
        item_bad = is_link
        if is_dir:
            size, used, bad, cut = _walk_bytes(full, budget)
            budget = max(0, budget - used)
            item_bad = item_bad or bad
            truncated = truncated or cut
        elif not is_link:
            try:
                size = os.path.getsize(full)
            except OSError:
                item_bad = True
        if item_bad:
            unreadable += 1
        items.append(
            {
                "path": os.path.normpath(full),
                "rel_path": name.replace(os.sep, "/"),
                "is_dir": is_dir,
                "bytes": size,
                "mtime": float(info.st_mtime),
                "unreadable": item_bad,
            }
        )
        total_bytes += size
    items.sort(key=lambda item: item["mtime"])
    return items, total_bytes, unreadable, truncated


def trash_usage(
    save_dir: str,
    retain_days: int = 30,
    max_gb: float = 2,
    now: Optional[Any] = None,
) -> Dict[str, Any]:
    root = os.path.join(str(save_dir), ".trash")
    current = now if now is not None else datetime.now(timezone.utc)
    if isinstance(current, (int, float)):
        current = datetime.fromtimestamp(float(current), timezone.utc)
    result: Dict[str, Any] = {
        "root": os.path.normpath(root),
        "count": 0,
        "bytes": 0,
        "oldest_at": "",
        "newest_at": "",
        "items": [],
        "truncated": False,
        "unreadable": 0,
        "limits": {"retain_days": retain_days, "max_gb": max_gb},
        "over_retention": False,
        "over_capacity": False,
        "scanned_at": current.isoformat(),
    }
    if not os.path.isdir(root):
        return result
    items, total_bytes, unreadable, truncated = _collect(root)
    result.update(
        {
            "count": len(items),
            "bytes": total_bytes,
            "items": items,
            "truncated": truncated,
            "unreadable": unreadable,
            "over_capacity": total_bytes > float(max_gb) * 1024 ** 3,
        }
    )
    if items:
        oldest = items[0]["mtime"]
        result["oldest_at"] = _iso(oldest)
        result["newest_at"] = _iso(items[-1]["mtime"])
        result["over_retention"] = (current.timestamp() - float(oldest)) > int(retain_days) * 86400
    return result