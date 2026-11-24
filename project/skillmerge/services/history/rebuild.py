from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Tuple

from ...util.errors import DomainError
from ...util.hashing import sha256_text, skill_dir_hash
from ...util.textnorm import normalize_paragraph
from ..merger.paragraphs import split_paragraphs
from ..merger.merge_service import MergeOptions
from ..parser.frontmatter import read_document
from ..parser.markdown import parse_markdown


def _chapter_map(root: str) -> Dict[str, Dict[str, Any]]:
    document = read_document(os.path.join(root, "SKILL.md"))
    headings = [item for item in parse_markdown(document.body).headings if int(item["level"]) > 1]
    lines = document.body.split("\n")
    if not headings:
        body = document.body.strip()
        return {"__body__": {"title": "正文", "hash": sha256_text(normalize_paragraph(body)), "paras": [item["hash"] for item in split_paragraphs(body)]}}
    minimum = min(int(item["level"]) for item in headings)
    result = {}
    for index, heading in enumerate(headings):
        if int(heading["level"]) != minimum:
            continue
        start = int(heading["line"])
        end = len(lines)
        for later in headings[index + 1:]:
            if int(later["level"]) <= minimum:
                end = int(later["line"]) - 1
                break
        body = "\n".join(lines[start:end]).strip("\n")
        norm = str(heading["norm"]) or str(heading["text"])
        result[norm] = {
            "title": str(heading["text"]),
            "hash": sha256_text(normalize_paragraph(body)),
            "paras": [item["hash"] for item in split_paragraphs(body)],
        }
    return result


def diff_chapters(old_root: str, new_root: str) -> List[Dict[str, Any]]:
    old = _chapter_map(old_root)
    new = _chapter_map(new_root)
    result = []
    for norm in sorted(set(new) - set(old), key=lambda item: item.encode("utf-8")):
        result.append({"op": "add", "title": new[norm]["title"], "norm": norm})
    for norm in sorted(set(old) - set(new), key=lambda item: item.encode("utf-8")):
        result.append({"op": "remove", "title": old[norm]["title"], "norm": norm})
    for norm in sorted(set(old) & set(new), key=lambda item: item.encode("utf-8")):
        if old[norm]["hash"] == new[norm]["hash"]:
            continue
        changed = len(set(old[norm]["paras"]) ^ set(new[norm]["paras"]))
        result.append({"op": "modify", "title": new[norm]["title"], "norm": norm, "changed_paragraphs": changed})
    return result


class RebuildService:
    def __init__(self, merge_service, skills_repo, artifacts_repo, registry=None) -> None:
        self.merge_service = merge_service
        self.skills_repo = skills_repo
        self.artifacts_repo = artifacts_repo
        self.registry = registry

    def _preflight(self, artifact, plan: Dict[str, Any]) -> None:
        if self.registry is None:
            return
        rule = self.registry.require(artifact.platform)
        name = str(plan.get("name") or artifact.name)
        checks = []
        maximum = int(rule.get("name", {}).get("max_length", 64))
        if len(name) > maximum:
            checks.append(f"名称超过 {maximum} 字符")
        lowered = name.lower()
        for part in rule.get("name", {}).get("forbidden_parts", []) or []:
            if str(part).lower() in lowered:
                checks.append(f"名称含保留词 {part}")
        if checks:
            raise DomainError(
                "EXPORT_BLOCKED",
                "重建前校验未通过：" + "；".join(checks),
                "修改产物名称后重建，例如 x-" + re.sub(r"[^a-z0-9-]+", "-", lowered).strip("-")[:40],
                466,
            )

    def _plan(self, artifact) -> Dict[str, Any]:
        path = os.path.join(artifact.dir_path, "merge_plan.json")
        if not os.path.isfile(path):
            raise DomainError("INVALID_ARGUMENT", "产物缺少 merge_plan.json", "仅合并产物可重建", 400)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                plan = json.load(handle)
        except (OSError, ValueError) as exc:
            raise DomainError("INVALID_ARGUMENT", "merge_plan.json 读取失败", str(exc), 400)
        if not isinstance(plan, dict) or not plan.get("sources"):
            raise DomainError("INVALID_ARGUMENT", "merge_plan 缺少 sources", "重新合并后再重建", 400)
        return plan

    def _skills(self, artifact, drop_missing: bool) -> Tuple[List[Any], List[Dict[str, Any]], List[str]]:
        skills = []
        changed = []
        missing = []
        for row in self.artifacts_repo.sources(artifact.id):
            skill = self.skills_repo.get(str(row["skill_id"]))
            if skill is None or skill.missing:
                missing.append(str(row["skill_id"]))
                continue
            current = skill_dir_hash(os.path.dirname(skill.path))
            if current != str(row["source_hash"]):
                changed.append({"skill_id": skill.id, "name": skill.name, "old": str(row["source_hash"]), "new": current})
                skill.content_hash = current
                with self.skills_repo.db.write_tx() as conn:
                    conn.execute("UPDATE skills SET content_hash=? WHERE id=?", (current, skill.id))
            skills.append(skill)
        if missing and not drop_missing:
            raise DomainError("INVALID_ARGUMENT", "存在缺失源，未允许剔除", "传 drop_missing_sources=true 或恢复源文件", 400, {"missing": missing})
        if not skills:
            raise DomainError("INVALID_ARGUMENT", "没有可重建的源技能", "恢复源后重试", 400)
        return skills, changed, missing

    def rebuild(self, artifact, drop_missing_sources: bool = False, job_id: str = "", cancel_token=None, progress=None) -> Dict[str, Any]:
        if artifact.status != "active":
            raise DomainError("NOT_FOUND", "产物不是 active 状态", "刷新历史列表后重试", 404)
        plan = self._plan(artifact)
        self._preflight(artifact, plan)
        skills, changed, missing = self._skills(artifact, drop_missing_sources)
        decisions = {str(item.get("key")): str(item.get("action")) for item in plan.get("decisions", []) if item.get("key")}
        options = MergeOptions(
            name=str(plan.get("name") or artifact.name),
            strategy=str(plan.get("strategy") or "keep-all"),
            platform=artifact.platform if artifact.platform in ("generic", "claude", "workbuddy", "chatgpt", "prompt-only") else "generic",
            decisions=decisions,
        )
        new_artifact = self.merge_service.merge(skills, options, job_id=job_id, cancel_token=cancel_token, progress=progress)
        diff = diff_chapters(artifact.dir_path, new_artifact["dir_path"])
        return {
            "artifact": new_artifact,
            "diff": diff,
            "changed_sources": changed,
            "missing_sources": missing,
            "source_updated": bool(changed),
        }