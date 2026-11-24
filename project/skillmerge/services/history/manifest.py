from __future__ import annotations

import os
from typing import Any, Dict, Iterable, List

from ...util.hashing import aggregate_hash, sha256_file


def _actual_files(root: str) -> Dict[str, Dict[str, Any]]:
    result = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in (".trash", "__pycache__"))
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or name == "manifest.json":
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            result[rel] = {"sha256": sha256_file(full), "size_bytes": os.path.getsize(full)}
    return result


def verify_manifest(root: str, manifest: Dict[str, Any], expected_hash: str = "") -> Dict[str, Any]:
    expected = {}
    for item in manifest.get("files", []):
        relative = item.get("rel_path") or item.get("path")
        if relative and item.get("sha256"):
            expected[str(relative)] = str(item["sha256"])
    actual = _actual_files(root)
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    modified = sorted(rel for rel in set(expected) & set(actual) if expected[rel] != actual[rel]["sha256"])
    aggregate = aggregate_hash((rel, item["sha256"]) for rel, item in actual.items())
    hash_mismatch = bool(expected_hash and aggregate != expected_hash)
    changed = missing + extra + modified
    return {
        "ok": not (missing or extra or modified or hash_mismatch),
        "missing": missing[:20],
        "extra": extra[:20],
        "modified": modified[:20],
        "changed_count": len(changed),
        "hash_mismatch": hash_mismatch,
        "aggregate": aggregate,
    }