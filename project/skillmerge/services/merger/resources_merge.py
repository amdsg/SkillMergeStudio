from __future__ import annotations

import os
import re
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List

from ..parser.resources import enumerate_resources

RESERVED = ("SKILL.md", "merge_plan.json", "manifest.json")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def normalize_rel(raw: str) -> str:
    value = str(raw or "").replace("\\", "/")
    if not value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise ValueError("绝对路径")
    if _CONTROL.search(value):
        raise ValueError("包含控制字符")
    path = PurePosixPath(value)
    parts = path.parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValueError("路径包含空段或 ..")
    return str(path)


def _split_name(rel: str):
    if "/" in rel:
        head, tail = rel.rsplit("/", 1)
        return head + "/", tail
    return "", rel


def _rename(rel: str, counter: int) -> str:
    prefix, name = _split_name(rel)
    stem, suffix = os.path.splitext(name)
    return f"{prefix}{stem}_{counter}{suffix}"


def _reserved_name(rel: str, used: Dict[str, str], sha: str) -> str:
    prefix, name = _split_name(rel)
    stem, suffix = os.path.splitext(name)
    if name in RESERVED:
        name = f"{stem}_res{suffix}"
    candidate = prefix + name
    counter = 2
    while candidate.casefold() in used and used[candidate.casefold()] != sha:
        candidate = _rename(prefix + name, counter)
        counter += 1
    return candidate


def _collect_entries(sources: Iterable[Dict[str, Any]]):
    entries: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []
    for source in sources:
        for resource in enumerate_resources(str(source["dir"])):
            try:
                rel = normalize_rel(str(resource["path"]))
            except ValueError as exc:
                decisions.append(
                    {
                        "rel_path": str(resource.get("path", "")),
                        "skill_id": source.get("skill_id", ""),
                        "skipped": "unsafe-path",
                        "reason": str(exc),
                    }
                )
                continue
            entries.append(
                {
                    "rel_path": rel,
                    "source_path": os.path.join(str(source["dir"]), rel.replace("/", os.sep)),
                    "sha256": str(resource["sha256"]),
                    "size_bytes": int(resource["size_bytes"]),
                    "kind": str(resource.get("kind", "other")),
                    "skill_id": source.get("skill_id", ""),
                    "source_index": int(source.get("source_index", 0)),
                }
            )
    entries.sort(key=lambda item: (item["rel_path"].casefold(), item["sha256"], item["source_index"]))
    return entries, decisions


def _assign_entries(entries: List[Dict[str, Any]], max_file_mb: int) -> Dict[str, Any]:
    kept: List[Dict[str, Any]] = []
    decisions: List[Dict[str, Any]] = []
    by_hash: Dict[str, str] = {}
    used: Dict[str, str] = {}
    for entry in entries:
        sha = entry["sha256"]
        if sha in by_hash:
            decisions.append(
                {
                    "rel_path": entry["rel_path"], "sha256": sha, "renamed_to": by_hash[sha],
                    "skipped": None, "deduped": True, "skill_id": entry["skill_id"],
                }
            )
            continue
        if max_file_mb and entry["size_bytes"] > int(max_file_mb) * 1024 * 1024:
            decisions.append(
                {
                    "rel_path": entry["rel_path"], "sha256": sha, "renamed_to": None,
                    "skipped": "file-too-large", "error": "V-BUNDLE-03",
                    "size_bytes": entry["size_bytes"], "skill_id": entry["skill_id"],
                }
            )
            continue
        target = _reserved_name(entry["rel_path"], used, sha)
        counter = 2
        while target.casefold() in used:
            target = _rename(entry["rel_path"], counter)
            counter += 1
        used[target.casefold()] = sha
        by_hash[sha] = target
        kept.append(dict(entry, renamed_to=target))
        decisions.append(
            {
                "rel_path": entry["rel_path"], "sha256": sha, "renamed_to": target,
                "skipped": None, "deduped": False, "skill_id": entry["skill_id"],
            }
        )
    kept.sort(key=lambda item: item["renamed_to"])
    return {"kept": kept, "decisions": decisions}


def merge_resources(
    sources: Iterable[Dict[str, Any]],
    max_file_mb: int = 0,
) -> Dict[str, Any]:
    entries, collect_decisions = _collect_entries(sources)
    assigned = _assign_entries(entries, max_file_mb)
    return {
        "kept": assigned["kept"],
        "decisions": collect_decisions + assigned["decisions"],
    }