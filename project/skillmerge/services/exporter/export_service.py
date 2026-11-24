from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ...storage.models import Artifact, MergeSource, dumps, loads
from ...storage.repos.artifacts_repo import ArtifactsRepo
from ...storage.repos.skills_repo import SkillsRepo
from ...util.errors import CancelledError, DomainError
from ..fsops import Staging, move_to_trash, reserve_dir
from ..parser.frontmatter import read_document
from .builder import payload_entries, prepare_spec, write_payload
from .desc import rewrite_description
from .installer import install_copy
from .manifest import build_manifest, write_manifest
from .namer import generate_name
from .packer import pack, unique_zip_path
from .platform_registry.format import format_info, manifest_format
from .prompt_pack import generate as generate_prompt
from .validate import dedupe_checks, errors, run_postflight, run_preflight


@dataclass
class ExportOptions:
    platform: str = "generic"
    mode: str = "dir"
    install_scope: str = "global"
    length_mode: str = "full"
    profile: str = "generic"
    examples: bool = False
    name_en: str = ""
    confirm_candidate: bool = False


class ExportService:
    def __init__(self, db, config, registry) -> None:
        self.db = db
        self.config = config
        self.registry = registry
        self.artifacts = ArtifactsRepo(db)
        self.skills = SkillsRepo(db)

    def _sources(self, artifact) -> List[Dict[str, Any]]:
        result = []
        for row in self.artifacts.sources(artifact.id):
            skill = self.skills.get(str(row["skill_id"]))
            result.append(
                {
                    "skill_id": str(row["skill_id"]),
                    "path": str(row["path"]),
                    "hash": str(row["source_hash"]),
                    "name": skill.name if skill else "",
                    "category": skill.category if skill else "",
                    "description": skill.description if skill else "",
                }
            )
        return result

    def _chapters(self, artifact_dir: str) -> List[str]:
        path = os.path.join(artifact_dir, "merge_plan.json")
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as handle:
                plan = json.load(handle)
            return [str(item.get("title", "")) for item in plan.get("chapter_map", [])]
        except (OSError, ValueError):
            return []

    def _meta(self, artifact) -> Dict[str, Any]:
        path = os.path.join(artifact.dir_path, "SKILL.md")
        if not os.path.isfile(path):
            raise DomainError("NOT_FOUND", "产物目录缺少 SKILL.md", "重新合并后再导出", 404)
        document = read_document(path)
        return {
            "document": document,
            "frontmatter": document.frontmatter,
            "description": document.description() or artifact.name,
            "chapters": self._chapters(artifact.dir_path),
        }

    def _name(self, rule, artifact, meta, options: ExportOptions) -> str:
        sources = self._sources(artifact)
        category = sources[0]["category"] if sources else ""
        return generate_name(
            rule,
            artifact.name,
            options.name_en,
            meta["frontmatter"],
            category,
            self.config.slug_map,
        )

    def _description(self, rule, artifact, meta, sources, name: str) -> str:
        trigger = sources[0]["description"] if sources else ""
        text, _level = rewrite_description(rule, meta["description"], sources, meta["chapters"], trigger)
        return text

    def _exports_root(self) -> str:
        root = os.path.join(self.config.save_dir, "exports")
        os.makedirs(root, exist_ok=True)
        return root

    def _cleanup(self, staging, committed: str, zip_path: Optional[str], save_dir: str) -> None:
        if staging is not None and getattr(staging, "root", ""):
            staging.trash()
        if committed and os.path.isdir(committed):
            move_to_trash(committed, save_dir)
        if zip_path and os.path.isfile(zip_path):
            move_to_trash(zip_path, save_dir)

    def export(self, artifact, options: ExportOptions, job_id: str = "", cancel_token=None, progress=None) -> Dict[str, Any]:
        if artifact.status != "active":
            raise DomainError("EXPORT_BLOCKED", "产物不是 active 状态", "重新合并或撤销后重建", 466)
        if not os.path.isdir(artifact.dir_path):
            raise DomainError("NOT_FOUND", "产物目录不存在", "重新合并后再导出", 404)
        entry = self.registry.entry(options.platform)
        if entry is None:
            raise DomainError("INVALID_ARGUMENT", f"平台规则不存在：{options.platform}", "选择已注册的平台", 400)
        if entry.evidence_level in ("failed_unreachable", "no_evidence", "discovery_source"):
            raise DomainError("PLATFORM_NOT_SELECTABLE", "该对象不是可导出的平台", "从平台清单选择", 400)
        if entry.verification_status == "unknown" and not options.confirm_candidate:
            raise DomainError(
                "PLATFORM_NOT_SELECTABLE",
                "候选平台规则未核验，需显式确认",
                "传入 confirm_candidate=true 后再导出",
                400,
            )
        rule = self._export_rule(entry)
        if rule.get("kind") == "prompt":
            return self._export_prompt(artifact, options, rule, job_id, cancel_token, progress)
        if options.mode == "install" and not (rule.get("install") or {}).get(options.install_scope):
            raise DomainError("EXPORT_BLOCKED", "该平台未配置安装目录", "改用 zip 或目录导出", 466)
        return self._export_skill(artifact, options, rule, job_id, cancel_token, progress)

    def preview_one(self, artifact, options: ExportOptions) -> Dict[str, Any]:
        if artifact.status != "active":
            raise DomainError("EXPORT_BLOCKED", "产物不是 active 状态", "重新合并或撤销后重建", 466)
        if not os.path.isdir(artifact.dir_path):
            raise DomainError("NOT_FOUND", "产物目录不存在", "重新合并后再导出", 404)
        entry = self.registry.entry(options.platform)
        if entry is None:
            raise DomainError("INVALID_ARGUMENT", f"平台规则不存在：{options.platform}", "选择已注册的平台", 400)
        if entry.evidence_level in ("failed_unreachable", "no_evidence", "discovery_source"):
            raise DomainError("PLATFORM_NOT_SELECTABLE", "该对象不是可导出的平台", "从平台清单选择", 400)
        rule = self._export_rule(entry)
        meta = self._meta(artifact)
        sources = self._sources(artifact)
        name = self._name(rule, artifact, meta, options)
        description = self._description(rule, artifact, meta, sources, name)
        if rule.get("kind") == "prompt":
            prompt = generate_prompt(artifact, rule, name, description, sources, options.length_mode, options.profile)
            spec = self._prompt_spec(name, description, prompt, options.mode)
        else:
            spec = prepare_spec(artifact.dir_path, rule, name, description, options.mode)
        checks = run_preflight(rule, spec)
        info = format_info(entry)
        files = [
            {
                "rel_path": str(item["rel_path"]),
                "size_bytes": int(item["size_bytes"]),
                "kind": str(item.get("kind") or "other"),
            }
            for item in spec.get("files", [])
        ]
        return {
            "platform": options.platform,
            "label": entry.label,
            "format": info,
            "install_available": bool(info["install_scopes"]),
            "requires_confirm": entry.verification_status == "unknown",
            "planned": {
                "name": name,
                "package_type": info["package_type"],
                "wrap": info["wrap"],
                "skill_md_path": info["skill_md_path"].replace("<name>", name),
                "files": files,
                "total_size_bytes": sum(item["size_bytes"] for item in files),
                "planned_entries": list(spec.get("planned_entries", [])),
            },
            "validation": checks,
            "warnings": list(spec.get("warnings", [])),
        }

    @staticmethod
    def _export_rule(entry) -> Dict[str, Any]:
        rule = entry.as_rule()
        if entry.verification_status == "unknown":
            rule["limits_source"] = "legacy_limits"
            rule["bundle"] = {"max_mb": 30, "max_files": 200, "max_file_mb": 10}
            rule["skill_md"] = {"max_lines": 5000, "max_bytes": 10485760}
            rule["description"] = {"max_chars": 1000, "style": "保守兜底，未核验"}
        else:
            rule["limits_source"] = "verified"
        return rule

    def _export_skill(self, artifact, options, rule, job_id, cancel_token, progress) -> Dict[str, Any]:
        save_dir = self.config.save_dir
        exports_root = self._exports_root()
        meta = self._meta(artifact)
        sources = self._sources(artifact)
        name = self._name(rule, artifact, meta, options)
        description = self._description(rule, artifact, meta, sources, name)
        spec = prepare_spec(artifact.dir_path, rule, name, description, options.mode)
        checks = run_preflight(rule, spec)
        if errors(checks):
            raise DomainError("EXPORT_BLOCKED", "preflight 校验未通过", "；".join(item["fix"] for item in errors(checks)), 466, {"checks": checks})
        if cancel_token is not None and cancel_token.is_set():
            raise CancelledError()
        if progress:
            progress("build", 0, 1, "构建适配目录")
        staging = Staging(save_dir)
        committed = ""
        zip_path = None
        installed_path = None
        try:
            write_payload(staging, spec)
            actual = dict(spec)
            actual["files"] = payload_entries(staging.root)
            actual["text"] = spec["text"]
            checks.extend(run_postflight(rule, actual))
            checks = dedupe_checks(checks)
            if errors(checks):
                raise DomainError("EXPORT_BLOCKED", "postflight 校验未通过", "；".join(item["fix"] for item in errors(checks)), 466, {"checks": checks})
            reserved = reserve_dir(exports_root, name)
            committed = staging.commit(reserved)
            if options.mode in ("zip", "download"):
                zip_path = unique_zip_path(exports_root, name)
                pack(committed, zip_path, spec["expected_prefix"])
            if options.mode == "install":
                installed_path, install_checks = install_copy(
                    committed, rule, options.install_scope, name, spec, os.getcwd(), save_dir
                )
                checks.extend(install_checks)
            final = dict(spec)
            final["files"] = payload_entries(committed)
            checks.extend(run_postflight(rule, final, zip_path))
            checks = dedupe_checks(checks)
            if errors(checks):
                raise DomainError("EXPORT_BLOCKED", "导出后校验未通过", "；".join(item["fix"] for item in errors(checks)), 466, {"checks": checks})
            fmt = manifest_format(rule)
            package_type = fmt.pop("package_type", "unknown")
            manifest = build_manifest(
                options.platform, rule, sources, committed, loads(artifact.plan_summary_json, {}),
                {"name": name, "description": description, "kind": "skill", "validation": checks,
                 "warnings": spec.get("warnings", []), "package_type": package_type, "format": fmt},
            )
            write_manifest(committed, manifest)
            record = self._record(artifact, options, name, "skill", committed, zip_path, installed_path, manifest, job_id)
            record.update({"validation": checks, "warnings": spec.get("warnings", []), "mode": options.mode})
            if zip_path:
                record["download_url"] = f"/api/artifacts/{record['artifact_id']}/download"
            return record
        except Exception:
            self._cleanup(staging, committed, zip_path, save_dir)
            raise

    @staticmethod
    def _prompt_spec(name, description, prompt, mode) -> Dict[str, Any]:
        return {
            "name": name,
            "description": description,
            "text": prompt["text"],
            "frontmatter": {"name": name, "description": description},
            "files": [
                {"rel_path": "prompt.md", "size_bytes": len(prompt["text"].encode("utf-8")), "kind": "document"},
                {"rel_path": "README.txt", "size_bytes": len(prompt["readme"].encode("utf-8")), "kind": "document"},
            ],
            "mode": mode,
            "expected_prefix": "",
            "layout_name": "",
            "planned_entries": [],
            "warnings": prompt["warnings"],
        }

    def _export_prompt(self, artifact, options, rule, job_id, cancel_token, progress) -> Dict[str, Any]:
        save_dir = self.config.save_dir
        exports_root = self._exports_root()
        meta = self._meta(artifact)
        sources = self._sources(artifact)
        name = self._name(rule, artifact, meta, options)
        description = self._description(rule, artifact, meta, sources, name)
        prompt = generate_prompt(
            artifact, rule, name, description, sources, options.length_mode, options.profile
        )
        spec = self._prompt_spec(name, description, prompt, options.mode)
        checks = run_preflight(rule, spec)
        if errors(checks):
            raise DomainError("EXPORT_BLOCKED", "提示词包校验未通过", "；".join(item["fix"] for item in errors(checks)), 466, {"checks": checks})
        if cancel_token is not None and cancel_token.is_set():
            raise CancelledError()
        staging = Staging(save_dir)
        committed = ""
        zip_path = None
        try:
            staging.write_text("prompt.md", prompt["text"])
            staging.write_text("README.txt", prompt["readme"])
            staging.write_json("manifest.json", prompt["manifest"])
            actual = dict(spec)
            actual["files"] = payload_entries(staging.root)
            checks.extend(run_postflight(rule, actual))
            checks = dedupe_checks(checks)
            if errors(checks):
                raise DomainError("EXPORT_BLOCKED", "提示词包后校验未通过", "；".join(item["fix"] for item in errors(checks)), 466, {"checks": checks})
            reserved = reserve_dir(exports_root, name)
            committed = staging.commit(reserved)
            if options.mode in ("zip", "download"):
                zip_path = unique_zip_path(exports_root, name)
                pack(committed, zip_path, "")
            fmt = manifest_format(rule)
            package_type = fmt.pop("package_type", "unknown")
            manifest = build_manifest(
                options.platform, rule, sources, committed, loads(artifact.plan_summary_json, {}),
                {"name": name, "description": description, "kind": "prompt", "validation": checks,
                 "tags": prompt["manifest"]["tags"], "token_estimate": prompt["manifest"]["token_estimate"],
                 "estimate": True, "length_mode": options.length_mode, "profile": options.profile,
                 "package_type": package_type, "format": fmt},
            )
            write_manifest(committed, manifest)
            record = self._record(artifact, options, name, "prompt", committed, zip_path, None, manifest, job_id)
            record.update({"validation": checks, "warnings": prompt["warnings"], "mode": options.mode, "length_mode": options.length_mode, "profile": options.profile})
            if zip_path:
                record["download_url"] = f"/api/artifacts/{record['artifact_id']}/download"
            return record
        except Exception:
            self._cleanup(staging, committed, zip_path, save_dir)
            raise

    def _record(self, artifact, options, name, kind, dir_path, zip_path, installed_path, manifest, job_id) -> Dict[str, Any]:
        artifact_id = uuid.uuid4().hex
        summary = loads(artifact.plan_summary_json, {})
        row = Artifact(
            id=artifact_id,
            name=name,
            slug=name,
            platform=options.platform,
            kind=kind,
            dir_path=dir_path,
            zip_path=zip_path,
            installed_path=installed_path,
            sha256=manifest["dir_sha256"],
            size_bytes=int(manifest["total_size_bytes"]),
            manifest_json=dumps(manifest),
            plan_summary_json=dumps(summary),
            status="active",
            created_at=manifest["created_at"],
            job_id=job_id or None,
        )
        sources = [
            MergeSource(
                artifact_id=artifact_id,
                skill_id=item["skill_id"],
                source_hash=item["hash"],
                path=item["path"],
            )
            for item in self._sources(artifact)
        ]
        try:
            self.artifacts.insert(row, sources)
        except Exception as exc:
            raise DomainError("STORAGE_ERROR", "导出产物登记失败", f"产物已保留：{dir_path}；{exc}", 500)
        return {
            "artifact_id": artifact_id,
            "name": name,
            "platform": options.platform,
            "kind": kind,
            "dir_path": dir_path,
            "zip_path": zip_path,
            "installed_path": installed_path,
            "size_bytes": row.size_bytes,
            "sha256": row.sha256,
            "sources_count": len(sources),
        }