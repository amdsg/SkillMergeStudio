from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ...util.errors import DomainError
from ...util.hashing import aggregate_hash, sha256_file
from ...util.timeutil import utc_now_iso
from ..fsops import is_within


def _files(root: str) -> List[Dict[str, Any]]:
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or name == "manifest.json":
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            entries.append({"rel_path": rel, "size_bytes": os.path.getsize(full), "sha256": sha256_file(full)})
    entries.sort(key=lambda item: item["rel_path"])
    return entries


def build_manifest(
    platform: str,
    rule: Dict[str, Any],
    sources: List[Dict[str, Any]],
    root: str,
    plan_summary: Dict[str, Any],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    files = _files(root)
    manifest = {
        "schema_version": 1,
        "platform": platform,
        "rule_verified_at": rule.get("verified_at", "unknown"),
        "rule_source": rule.get("source", "unknown"),
        "files": files,
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "dir_sha256": aggregate_hash([(item["rel_path"], item["sha256"]) for item in files]),
        "sources": sources,
        "plan_summary": plan_summary,
        "created_at": utc_now_iso(),
        "tool_version": "1.0.0",
    }
    manifest.update(extra or {})
    return manifest


def write_manifest(root: str, manifest: Dict[str, Any]) -> str:
    path = os.path.join(root, "manifest.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def resolve_download(artifact, rel_path: str = "") -> Dict[str, str]:
    manifest = artifact.manifest()
    allowed = {str(item["rel_path"]) for item in manifest.get("files", [])}
    if rel_path:
        rel = str(rel_path).replace("\\", "/")
        if rel not in allowed or ".." in rel.split("/") or rel.startswith("/"):
            raise DomainError("NOT_FOUND", "下载路径不在 manifest 清单中", "使用 manifest 内的相对路径", 404)
        target = os.path.join(artifact.dir_path, rel.replace("/", os.sep))
        if not is_within(target, artifact.dir_path) or not os.path.isfile(target):
            raise DomainError("PATH_OUT_OF_BOUNDS", "下载路径越界", "使用产物目录内文件", 400)
        return {"path": target, "filename": os.path.basename(target)}
    if artifact.zip_path and os.path.isfile(artifact.zip_path):
        return {"path": artifact.zip_path, "filename": os.path.basename(artifact.zip_path)}
    raise DomainError("NOT_FOUND", "该产物没有可下载的 zip", "先执行 zip 或 download 导出", 404)