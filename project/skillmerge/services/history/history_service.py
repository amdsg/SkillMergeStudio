from __future__ import annotations

import os
from typing import Any, Dict, List

from .manifest import verify_manifest



def artifact_row(artifact, source_count: int) -> Dict[str, Any]:
    return {
        "id": artifact.id,
        "created_at": artifact.created_at,
        "name": artifact.name,
        "platform": artifact.platform,
        "source_count": source_count,
        "size_bytes": artifact.size_bytes,
        "status": artifact.status,
        "undone_at": artifact.undone_at,
        "dir_path": artifact.dir_path,
        "zip_path": artifact.zip_path,
        "installed_path": artifact.installed_path,
    }


def list_history(repo, limit: int = 50, offset: int = 0, skills=None, platform: str = "") -> Dict[str, Any]:
    rows = repo.list(limit, offset, platform)
    items = []
    for row in rows:
        artifact = repo.get(str(row["id"]))
        if artifact is None:
            continue
        status = artifact.status
        if status == "active" and not os.path.isdir(artifact.dir_path):
            status = "missing"
        item = artifact_row(artifact, len(repo.sources(artifact.id)))
        item["status"] = status
        item["source_updated"] = False
        item["changed_sources"] = []
        item["missing_sources"] = []
        if skills is not None and status == "active":
            report = source_status(repo, skills, artifact)
            item["source_updated"] = report["source_updated"]
            item["changed_sources"] = report["changed"]
            item["missing_sources"] = report["missing"]
        items.append(item)
    return {"items": items, "page": {"limit": limit, "offset": offset, "total": repo.count(platform)}}


def detail(repo, artifact, skills=None) -> Dict[str, Any]:
    manifest = artifact.manifest()
    verification = verify_manifest(artifact.dir_path, manifest, artifact.sha256)
    item = artifact_row(artifact, len(repo.sources(artifact.id)))
    item["status"] = "missing" if artifact.status == "active" and not os.path.isdir(artifact.dir_path) else artifact.status
    item["source_updated"] = False
    item["changed_sources"] = []
    item["missing_sources"] = []
    if skills is not None and item["status"] == "active":
        report = source_status(repo, skills, artifact)
        item["source_updated"] = report["source_updated"]
        item["changed_sources"] = report["changed"]
        item["missing_sources"] = report["missing"]
    return {
        "artifact": item,
        "manifest": manifest,
        "files": manifest.get("files", []),
        "validation": manifest.get("validation", []),
        "verification": verification,
    }


def artifacts_for_skill(repo, skill_id: str) -> Dict[str, Any]:
    rows = repo.artifacts_for_skill(skill_id)
    return {"items": [artifact_row(repo.get(str(row["id"])), len(repo.sources(str(row["id"])))) for row in rows]}


def source_status(repo, skills, artifact) -> Dict[str, Any]:
    from ...util.hashing import skill_dir_hash


    changed = []
    missing = []
    for row in repo.sources(artifact.id):
        skill = skills.get(str(row["skill_id"]))
        if skill is None or skill.missing:
            missing.append(str(row["skill_id"]))
            continue
        current = skill_dir_hash(os.path.dirname(skill.path))
        if current != str(row["source_hash"]):
            changed.append({"skill_id": str(row["skill_id"]), "name": skill.name, "old": str(row["source_hash"]), "new": current})
    return {"changed": changed, "missing": missing, "source_updated": bool(changed or missing)}