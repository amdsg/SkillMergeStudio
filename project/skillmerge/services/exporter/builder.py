from __future__ import annotations

import os
from typing import Any, Dict, List

from ...util.errors import DomainError
from ..fsops import Staging
from ..parser.frontmatter import read_document
from ..parser.resources import classify
from .desc import default_frontmatter
from .plan import build_adapt_plan, layout_prefix, render_frontmatter

EXCLUDE = {"manifest.json"}


def _resource_files(source_dir: str) -> List[Dict[str, Any]]:
    files = []
    for dirpath, dirnames, filenames in os.walk(source_dir):
        dirnames[:] = sorted(name for name in dirnames if name not in ("__pycache__", ".git"))
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, source_dir).replace(os.sep, "/")
            if rel in EXCLUDE or name.lower().endswith(".zip"):
                continue
            files.append(
                {
                    "rel_path": rel,
                    "source_path": full,
                    "size_bytes": os.path.getsize(full),
                    "kind": classify(rel),
                }
            )
    files.sort(key=lambda item: item["rel_path"])
    return files


def prepare_spec(
    artifact_dir: str,
    rule: Dict[str, Any],
    name: str,
    description: str,
    mode: str = "dir",
) -> Dict[str, Any]:
    skill_path = os.path.join(artifact_dir, "SKILL.md")
    if not os.path.isfile(skill_path):
        raise DomainError("EXPORT_BLOCKED", "产物缺少 SKILL.md", "重新合并后再导出", 466)
    document = read_document(skill_path)
    if document.parse_error:
        raise DomainError("EXPORT_BLOCKED", "产物 frontmatter 解析失败", "修复 SKILL.md 后重新导出", 466)
    frontmatter, warnings = default_frontmatter(rule, name, description, document.frontmatter)
    text = render_frontmatter(frontmatter) + "\n" + document.body.lstrip("\n")
    files = [{"rel_path": "SKILL.md", "source_path": skill_path, "size_bytes": len(text.encode("utf-8")), "kind": "document"}]
    for item in _resource_files(artifact_dir):
        if item["rel_path"] != "SKILL.md":
            files.append(item)
    prefix = layout_prefix(rule, name)
    plan = build_adapt_plan(rule, name, frontmatter)
    return {
        "name": name,
        "description": description,
        "text": text,
        "frontmatter": frontmatter,
        "files": files,
        "mode": mode,
        "expected_prefix": prefix,
        "layout_name": name if mode in ("zip", "download") else "",
        "planned_entries": [prefix + item["rel_path"] for item in files],
        "warnings": warnings,
        "plan": plan,
    }


def write_payload(staging: Staging, spec: Dict[str, Any]) -> None:
    staging.write_text("SKILL.md", spec["text"])
    for item in spec["files"]:
        if item["rel_path"] == "SKILL.md":
            continue
        staging.copy_file(item["source_path"], item["rel_path"])


def payload_entries(root: str) -> List[Dict[str, Any]]:
    entries = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel in EXCLUDE:
                continue
            entries.append({"rel_path": rel, "size_bytes": os.path.getsize(full), "kind": classify(rel)})
    entries.sort(key=lambda item: item["rel_path"])
    return entries