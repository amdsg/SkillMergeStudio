from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...config.paths import expand_path
from ...storage.models import Artifact, MergeSource, dumps
from ...storage.repos.artifacts_repo import ArtifactsRepo
from ...storage.repos.skills_repo import SkillsRepo
from ...util.errors import CancelledError, DomainError
from ...util.hashing import aggregate_hash, sha256_text, skill_dir_hash
from ...util.timeutil import utc_now_iso
from ..ai_client import AIClient
from ..fsops import Staging, assert_inside, is_system_path, move_to_trash, reserve_dir, safe_component
from ..parser.frontmatter import read_document
from .ai_suggest import build_prompt, parse_suggestions
from .align import align_sources, extract_chapters
from .assemble import (
    assemble_document,
    default_description,
    estimate_volume,
    prepare_chapters,
    trim_suggestions,
)
from .dependencies import aggregate
from .plan import build_plan, canonical_json, plan_hash
from .resources_merge import merge_resources


@dataclass
class MergeOptions:
    name: str
    strategy: str = "keep-all"
    platform: str = "generic"
    save_dir: str = ""
    copy_assets: bool = True
    decisions: Dict[str, str] = field(default_factory=dict)
    aliases: List[Dict[str, str]] = field(default_factory=list)
    description: str = ""
    use_ai: bool = False
    confirm_ai: bool = False
    ai_confirm_keys: List[str] = field(default_factory=list)


class MergeService:
    def __init__(self, db, config, registry) -> None:
        self.db = db
        self.config = config
        self.registry = registry
        self.skills = SkillsRepo(db)
        self.artifacts = ArtifactsRepo(db)

    def _resolve_save_dir(self, options: MergeOptions) -> str:
        base = expand_path(self.config.save_dir)
        target = expand_path(options.save_dir, base) if options.save_dir else base
        assert_inside(target, base)
        if is_system_path(target):
            raise DomainError("PATH_OUT_OF_BOUNDS", "拒绝写入系统目录", "选择用户目录下的保存路径", 400)
        return target

    def _load_sources(self, skills: List[Any], cancel_token=None) -> List[Dict[str, Any]]:
        loadeds = []
        labels = {}
        for index, skill in enumerate(skills):
            if cancel_token is not None and cancel_token.is_set():
                raise CancelledError()
            if skill is None or skill.missing:
                raise DomainError("MERGE_SOURCE_MISSING", "合并源不存在或已缺失", "重新扫描并移除失效源", 400)
            path = skill.path
            directory = os.path.dirname(path)
            try:
                document = read_document(path)
            except OSError as exc:
                raise DomainError("MERGE_SOURCE_MISSING", f"无法读取源：{path}", f"检查文件权限：{exc}", 400)
            label = os.path.basename(directory)
            labels[label] = labels.get(label, 0) + 1
            if labels[label] > 1:
                label = f"{label}#{labels[label]}"
            chapters = extract_chapters(document.body, skill.id, index, label)
            loadeds.append(
                {
                    "skill": skill,
                    "skill_id": skill.id,
                    "name": skill.name,
                    "description": skill.description,
                    "category": skill.category,
                    "platform": skill.platform_origin,
                    "path": path,
                    "dir": directory,
                    "source_hash": skill.content_hash,
                    "frontmatter": document.frontmatter,
                    "body": document.body,
                    "chapters": chapters,
                    "parse_error": document.parse_error,
                    "warnings": document.warnings,
                    "source_label": label,
                }
            )
        return loadeds

    @staticmethod
    def _sources_meta(loadeds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "skill_id": item["skill_id"],
                "source_hash": item["source_hash"],
                "path": item["path"],
                "name": item["name"],
                "category": item["category"],
                "platform": item["platform"],
                "frontmatter": item["frontmatter"],
                "dir": item["dir"],
            }
            for item in loadeds
        ]

    def _build(self, skills: List[Any], options: MergeOptions, cancel_token=None) -> Dict[str, Any]:
        rule = self.registry.require(options.platform)
        loadeds = self._load_sources(skills, cancel_token)
        chapter_map = align_sources([item["chapters"] for item in loadeds], options.aliases, cancel_token)
        dependencies = [dep for item in loadeds for dep in item["skill"].dependencies()]
        packages = aggregate(dependencies)
        resources = merge_resources(
            [{"skill_id": item["skill_id"], "dir": item["dir"], "source_index": index}
             for index, item in enumerate(loadeds)],
            max_file_mb=int(rule["bundle"]["max_file_mb"]),
        )
        prepared_result = prepare_chapters(chapter_map, options.strategy, options.decisions)
        dedup_payload = dict(prepared_result)
        dedup_payload["omitted"] = [
            entry for group in prepared_result["chapters"] for entry in group["omitted"]
        ]
        sources_meta = self._sources_meta(loadeds)
        description = options.description or default_description(options.name, sources_meta)
        plan = build_plan(
            options.name,
            options.strategy,
            sources_meta,
            chapter_map,
            resources["decisions"],
            packages,
            dedup_payload,
            options.decisions,
        )
        text = assemble_document(
            options.name,
            description,
            sources_meta,
            prepared_result["chapters"],
            packages,
            prepared_result,
            options.strategy,
        )
        size = estimate_volume(text, resources["kept"])
        limit_bytes = int(rule["bundle"]["max_mb"]) * 1024 * 1024
        suggestions = trim_suggestions(prepared_result["chapters"], size, limit_bytes) if limit_bytes else []
        validation = self._validate(
            options, rule, text, prepared_result, resources, size, loadeds
        )
        return {
            "rule": rule,
            "loadeds": loadeds,
            "sources": sources_meta,
            "chapter_map": chapter_map,
            "prepared": prepared_result,
            "packages": packages,
            "resources": resources,
            "plan": plan,
            "plan_hash": plan_hash(plan),
            "text": text,
            "size": size,
            "suggestions": suggestions,
            "validation": validation,
            "diff": self._diff(loadeds, chapter_map, prepared_result),
            "warnings": self._warnings(loadeds, prepared_result),
        }

    def _validate(self, options, rule, text, prepared, resources, size, loadeds) -> List[Dict[str, str]]:
        checks: List[Dict[str, str]] = []
        name_max = int(rule["name"]["max_length"])
        if not options.name.strip():
            checks.append({"id": "V-NAME-01", "level": "error", "message": "产物名称为空", "fix": "填写 1–120 字符的名称"})
        elif len(options.name) > name_max:
            checks.append({"id": "V-NAME-02", "level": "error", "message": f"名称超过 {name_max} 字符", "fix": "缩短名称"})
        description = default_description(options.name, [{"name": item["name"], "category": item["category"]} for item in loadeds])
        if len(description) > int(rule["description"]["max_chars"]):
            checks.append({"id": "V-DESC-01", "level": "warn", "message": "描述超限，导出时将重写", "fix": "M3 导出器会按模板重写"})
        if not prepared["chapters"]:
            checks.append({"id": "V-MD-01", "level": "error", "message": "合并后正文为空", "fix": "检查源 SKILL.md 是否包含正文"})
        h1_count = sum(1 for line in text.split("\n") if line.startswith("# "))
        if h1_count != 1:
            checks.append({"id": "V-MD-03", "level": "error", "message": f"一级标题数量为 {h1_count}", "fix": "保留唯一产物标题"})
        limit_bytes = int(rule["bundle"]["max_mb"]) * 1024 * 1024
        if limit_bytes and size > limit_bytes:
            checks.append(
                {
                    "id": "V-BUNDLE-01",
                    "level": "error",
                    "message": f"体积 {size} 字节超过平台上限 {limit_bytes} 字节",
                    "fix": "按预览中的裁剪建议删减章节；系统不会截断正文",
                }
            )
        if len(resources["kept"]) + 2 > int(rule["bundle"]["max_files"]):
            checks.append({"id": "V-BUNDLE-02", "level": "error", "message": "文件数超过平台上限", "fix": "移除部分资源"})
        for decision in resources["decisions"]:
            if decision.get("error"):
                checks.append(
                    {
                        "id": "V-BUNDLE-03",
                        "level": "error",
                        "message": f'资源 {decision.get("rel_path")} 超过单文件上限',
                        "fix": "手动压缩或移除该资源",
                    }
                )
        for loaded in loadeds:
            if loaded["parse_error"]:
                checks.append(
                    {
                        "id": "V-PARSE-01",
                        "level": "warn",
                        "message": f'{loaded["name"]} frontmatter 解析失败，仅按原始正文参与',
                        "fix": "修复源 frontmatter 后重新扫描",
                    }
                )
        return checks

    def _diff(self, loadeds, chapter_map, prepared) -> List[Dict[str, Any]]:
        if not loadeds:
            return []
        first_id = loadeds[0]["skill_id"]
        result = []
        for group in prepared["chapters"]:
            member_ids = {member["skill_id"] for member in group["members"]}
            if first_id in member_ids and len(group["members"]) > 1:
                op = "modify"
            elif first_id in member_ids:
                op = "keep"
            else:
                op = "add"
            result.append({"op": op, "title": group["title"], "sim": group.get("sim")})
        for group in prepared["chapters"]:
            for item in group["omitted"]:
                if item["skill_id"] == first_id:
                    result.append({"op": "remove", "title": group["title"], "sim": group.get("sim")})
        order = {"add": 0, "remove": 1, "modify": 2, "keep": 3}
        result.sort(key=lambda item: (order.get(item["op"], 9), str(item["title"])))
        return result

    def _warnings(self, loadeds, prepared) -> List[Dict[str, str]]:
        warnings = list(prepared["warnings"])
        for loaded in loadeds:
            warnings.extend(loaded["warnings"])
        return warnings

    def preview(self, skills: List[Any], options: MergeOptions) -> Dict[str, Any]:
        if len(skills) > 20:
            raise DomainError("INVALID_ARGUMENT", "预览最多 20 个源", "减少选择数量后重试", 400)
        total = sum(int(skill.size_bytes or 0) for skill in skills if skill)
        if total > 8 * 1024 * 1024:
            raise DomainError("INVALID_ARGUMENT", "预览源总大小超过 8MB", "减少选择数量后重试", 400)
        built = self._build(skills, options)
        conflicts = []
        for group in built["prepared"]["chapters"]:
            if group["decision"] != "conflict" or len(group["members"]) < 2:
                continue
            first, second = group["members"][0], group["members"][1]
            conflicts.append(
                {
                    "key": group["key"],
                    "title": group["title"],
                    "sim": group.get("sim"),
                    "source_a": first["source_label"],
                    "source_b": second["source_label"],
                    "text_a": "\n\n".join(first["paragraphs"]),
                    "text_b": "\n\n".join(second["paragraphs"]),
                    "suggested_action": "keepBoth",
                }
            )
        chapters = [
            {
                "key": group["key"],
                "title": group["title"],
                "level": group["level"],
                "from": [
                    {"skill_id": member["skill_id"], "line": member.get("line", 0)}
                    for member in group["members"]
                ],
                "decision": group["decision"],
                "sim": group.get("sim"),
            }
            for group in built["prepared"]["chapters"]
        ]
        return {
            "chapters": chapters,
            "conflicts": conflicts,
            "dedup": {
                "duplicate_paragraphs": built["prepared"]["duplicate_paragraphs"],
                "suggested_near_dupes": built["prepared"]["suggested_near_dupes"],
            },
            "size_estimate": {
                "bytes": built["size"],
                "method": "sum-of-parts",
                "suggestions": built["suggestions"],
            },
            "validation": built["validation"],
            "diff": built["diff"],
            "warnings": built["warnings"],
            "plan_summary": {
                "strategy": options.strategy,
                "sources_count": len(built["sources"]),
                "plan_hash": built["plan_hash"],
                "chapters": len(built["prepared"]["chapters"]),
            },
        }

    def merge(self, skills: List[Any], options: MergeOptions, job_id: str = "", cancel_token=None, progress=None) -> Dict[str, Any]:
        save_dir = self._resolve_save_dir(options)
        built = self._build(skills, options, cancel_token)
        errors = [item for item in built["validation"] if item["level"] == "error"]
        if errors:
            raise DomainError("EXPORT_BLOCKED", "合并前校验未通过", "；".join(item["fix"] for item in errors), 466)
        ai_payload = None
        if options.use_ai:
            if progress:
                progress("ai", 0, 1, "生成 AI 建议稿（不写入正文）")
            ai_payload = self._ai_suggest(options, built, cancel_token)
        staging = Staging(save_dir)
        reserved = ""
        committed = ""
        try:
            if progress:
                progress("write", 0, 1, "写入 staging")
            staging.write_text("SKILL.md", built["text"])
            staging.write_json("merge_plan.json", built["plan"])
            if ai_payload is not None:
                staging.write_json("ai_suggestions.json", ai_payload)
            if options.copy_assets:
                for resource in built["resources"]["kept"]:
                    staging.copy_file(resource["source_path"], resource["renamed_to"])
            if cancel_token is not None and cancel_token.is_set():
                raise CancelledError()
            self._verify_sources(built["sources"])
            manifest = self._manifest(options, built, staging.root)
            if ai_payload is not None:
                manifest["ai"] = self._ai_manifest(ai_payload)
            staging.write_json("manifest.json", manifest)
            reserved = reserve_dir(save_dir, options.name)
            committed = staging.commit(reserved)
            record = self._record(options, built, manifest, committed, job_id)
            if ai_payload is not None:
                record["ai"] = self._ai_record(ai_payload)
            return record
        except CancelledError:
            staging.trash()
            self._remove_empty(reserved)
            raise
        except Exception:
            staging.trash()
            self._remove_empty(reserved)
            if committed:
                move_to_trash(committed, save_dir)
            raise

    @staticmethod
    def _remove_empty(path: str) -> None:
        if path and os.path.isdir(path) and not os.listdir(path):
            try:
                os.rmdir(path)
            except OSError:
                pass

    def _verify_sources(self, sources: List[Dict[str, Any]]) -> None:
        for source in sources:
            current = skill_dir_hash(source["dir"])
            if current != source["source_hash"]:
                raise DomainError(
                    "MERGE_SOURCE_CHANGED",
                    f'源已变更：{source["name"]}',
                    "重新扫描后再合并，避免使用过期内容",
                    409,
                )

    def _ai_suggest(self, options: MergeOptions, built: Dict[str, Any], cancel_token=None) -> Dict[str, Any]:
        ai = getattr(self.config, "ai", None)
        payload: Dict[str, Any] = {
            "ok": False,
            "applied": False,
            "model": str(getattr(ai, "model", "") or ""),
            "prompt_hash": "",
            "tokens": 0,
            "reason": "",
            "suggestions": [],
        }
        if ai is None or not getattr(ai, "enabled", False) or not ai.base_url or not ai.model:
            payload["reason"] = "AI 未启用或未配置，已回退规则合并"
            return payload
        if cancel_token is not None and cancel_token.is_set():
            raise CancelledError()
        chapters = [
            {
                "key": str(group["key"]),
                "title": str(group["title"]),
                "text": "\n\n".join(
                    paragraph for member in group["members"] for paragraph in member.get("paragraphs", [])
                ),
            }
            for group in built["prepared"]["chapters"]
        ]
        prompt = build_prompt(options.name, chapters)
        payload["prompt_hash"] = sha256_text(prompt)
        client = AIClient(ai.base_url, ai.api_key, ai.model, timeout=int(getattr(ai, "timeout", 90) or 90))
        try:
            response = client.suggest_merge(prompt)
            suggestions = parse_suggestions(response["content"], {item["key"]: item for item in chapters})
        except Exception as exc:  # noqa: BLE001
            payload["reason"] = (str(exc) or "AI 建议失败")[:300]
            return payload
        payload.update(
            {
                "ok": True,
                "model": str(response.get("model") or ai.model),
                "tokens": int(response.get("tokens", 0) or 0),
                "suggestions": suggestions,
            }
        )
        return payload

    @staticmethod
    def _ai_manifest(ai_payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": bool(ai_payload.get("ok")),
            "applied": False,
            "model": ai_payload.get("model", ""),
            "prompt_hash": ai_payload.get("prompt_hash", ""),
            "tokens": int(ai_payload.get("tokens", 0) or 0),
            "reason": ai_payload.get("reason", ""),
            "suggest_count": len(ai_payload.get("suggestions") or []),
        }

    @staticmethod
    def _ai_record(ai_payload: Dict[str, Any]) -> Dict[str, Any]:
        payload = MergeService._ai_manifest(ai_payload)
        payload.pop("suggest_count", None)
        payload["suggestions"] = [
            {
                "key": item["key"],
                "title": item["title"],
                "before_chars": item["before_chars"],
                "after_chars": item["after_chars"],
                "diff": item["diff"],
            }
            for item in ai_payload.get("suggestions") or []
        ]
        return payload

    def _manifest(self, options: MergeOptions, built: Dict[str, Any], staging_root: str) -> Dict[str, Any]:
        entries = []
        for dirpath, dirnames, filenames in os.walk(staging_root):
            dirnames[:] = sorted(dirnames)
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, staging_root).replace(os.sep, "/")
                import hashlib

                digest = hashlib.sha256()
                with open(full, "rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                entries.append({"path": rel, "size_bytes": os.path.getsize(full), "sha256": digest.hexdigest()})
        entries.sort(key=lambda item: item["path"])
        dir_hash = aggregate_hash([(item["path"], item["sha256"]) for item in entries])
        return {
            "artifact_id": "",
            "name": options.name,
            "slug": safe_component(options.name),
            "platform": options.platform,
            "kind": "skill",
            "created_at": utc_now_iso(),
            "tool_version": "1.0.0",
            "generator": "skillmerge-studio/1.0.0",
            "rule_verified_at": built["rule"].get("verified_at", "unknown"),
            "plan_sha256": sha256_text(canonical_json(built["plan"])),
            "dir_sha256": dir_hash,
            "total_size_bytes": sum(item["size_bytes"] for item in entries),
            "sources": [
                {"skill_id": source["skill_id"], "path": source["path"], "hash": source["source_hash"]}
                for source in built["sources"]
            ],
            "files": entries,
            "validation": built["validation"],
            "merge_plan": "./merge_plan.json",
            "strategy": options.strategy,
        }

    def _record(self, options: MergeOptions, built: Dict[str, Any], manifest: Dict[str, Any], final_path: str, job_id: str) -> Dict[str, Any]:
        artifact_id = uuid.uuid4().hex
        manifest["artifact_id"] = artifact_id
        created_at = manifest["created_at"]
        summary = {
            "strategy": options.strategy,
            "sources_count": len(built["sources"]),
            "plan_hash": built["plan_hash"],
            "chapters": len(built["prepared"]["chapters"]),
        }
        artifact = Artifact(
            id=artifact_id,
            name=options.name,
            slug=safe_component(options.name),
            platform=options.platform,
            kind="skill",
            dir_path=final_path,
            sha256=manifest["dir_sha256"],
            size_bytes=int(manifest["total_size_bytes"]),
            manifest_json=dumps(manifest),
            plan_summary_json=dumps(summary),
            status="active",
            created_at=created_at,
            job_id=job_id or None,
        )
        sources = [
            MergeSource(
                artifact_id=artifact_id,
                skill_id=source["skill_id"],
                source_hash=source["source_hash"],
                path=source["path"],
            )
            for source in built["sources"]
        ]
        try:
            self.artifacts.insert(artifact, sources)
        except Exception as exc:
            raise DomainError("STORAGE_ERROR", "产物已写入但数据库登记失败", f"产物已备份到 .trash：{exc}", 500)
        return {
            "artifact_id": artifact_id,
            "name": options.name,
            "slug": artifact.slug,
            "platform": options.platform,
            "dir_path": final_path,
            "size_bytes": artifact.size_bytes,
            "sha256": artifact.sha256,
            "sources_count": len(sources),
            "plan_summary": summary,
            "validation": built["validation"],
            "warnings": built["warnings"],
        }