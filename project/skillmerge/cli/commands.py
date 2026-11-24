from __future__ import annotations

import json
import os
import time
from typing import List

from .output import emit, emit_error, log
from ..app import build_app, make_context, run_server
from ..services.classifier.classifier_service import ClassifierService
from ..services.exporter.builder import prepare_spec
from ..services.exporter.desc import rewrite_description
from ..services.exporter.export_service import ExportOptions, ExportService
from ..services.exporter.namer import generate_name
from ..services.exporter.platform_registry.params import validate_platform_params
from ..services.exporter.platform_registry.query import query_platforms
from ..services.exporter.registry import PlatformRegistry
from ..services.exporter.validate import errors, run_postflight, run_preflight
from ..services.merger.merge_service import MergeOptions
from ..services.parser.frontmatter import read_document
from ..services.scanner.scanner_service import ScanOptions, ScannerService
from ..config import paths
from ..config.loader import load_config
from ..storage.db import Database
from ..util.errors import DomainError


def _context(args):
    data_dir = args.data_dir or paths.data_dir()
    config, warnings = load_config(data_dir)
    for warning in warnings:
        log(f"{warning.get('code')}: {warning.get('message')}")
    db = Database(paths.db_path(data_dir))
    db.initialize()
    return make_context(data_dir, config, db)


def _split_ids(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").replace(";", ",").split(",") if item.strip()]


def run_scan(args) -> int:
    data_dir = args.data_dir or paths.data_dir()
    config, warnings = load_config(data_dir)
    for warning in warnings:
        log(f"{warning.get('code')}: {warning.get('message')}")
    db = Database(paths.db_path(data_dir))
    db.initialize()
    try:
        service = ScannerService(db, config)
        options = ScanOptions(
            roots=list(args.root),
            mode="probe",
            depth=args.depth or config.scan_depth,
            limit=args.limit or config.scan_limit,
            time_limit=args.time_limit or config.scan_time_limit,
            refresh=bool(args.refresh),
        )
        started = time.monotonic()
        result = service.scan(options=options)
        elapsed = time.monotonic() - started
        log(
            f"扫描完成：发现 {result['stats'].get('found', 0)} 个，"
            f"新增 {result['stats'].get('new', 0)} 个，耗时 {elapsed:.2f}s"
        )
        emit({"ok": True, "data": result})
        return 0
    finally:
        db.close_all()


def run_serve(args) -> int:
    server = build_app(
        host=args.host,
        preferred_port=args.port,
        data_dir=args.data_dir or None,
        check_pid=not args.force,
    )
    if server is None:
        return 0
    return run_server(server, args.host)


def run_platforms(args) -> int:
    registry = PlatformRegistry(paths.platforms_dir())
    try:
        params = validate_platform_params(
            {
                "kind": args.kind,
                "group": args.group,
                "verified": args.verified,
                "evidence": args.evidence,
                "q": args.q,
                "sort": args.sort,
                "limit": args.limit,
                "offset": args.offset,
            },
            registry,
        )
    except DomainError as exc:
        emit_error(exc.code, exc.message, exc.fix)
        return 2
    data = query_platforms(registry, params)
    emit({"ok": True, "data": data})
    log(f"counts={data['counts']} diagnostics={len(data['diagnostics'])}")
    return 1 if any(item.get("severity") == "error" for item in data["diagnostics"]) else 0


def run_classify(args) -> int:
    ctx = _context(args)
    try:
        service = ClassifierService(ctx.db, ctx.config)
        result = service.classify(
            _split_ids(args.skill_ids) or None,
            use_ai=bool(args.use_ai),
            confirm_ai=bool(args.confirm_ai),
        )
        emit({"ok": True, "data": result})
        log(f"分类完成：更新 {result.get('updated', 0)} 条")
        return 0
    finally:
        ctx.db.close_all()


def run_merge(args) -> int:
    ctx = _context(args)
    try:
        sources = _split_ids(args.sources)
        if not sources:
            emit_error("INVALID_ARGUMENT", "sources 不能为空", "用 --sources id1,id2 传入技能 id")
            return 2
        skills = []
        for skill_id in sources:
            skill = ctx.skills_repo.get(skill_id)
            if skill is None:
                emit_error("NOT_FOUND", f"技能不存在：{skill_id}", "先运行 scan 并核对技能 id")
                return 2
            skills.append(skill)
        options = MergeOptions(
            name=args.name,
            strategy=args.strategy,
            platform=args.platform,
            save_dir=args.out or "",
            use_ai=bool(args.use_ai),
            confirm_ai=bool(args.confirm_ai),
        )
        result = ctx.merge_service.merge(skills, options)
        emit({"ok": True, "data": result})
        log(f"合并完成：{result.get('dir_path', '')}")
        return 0
    finally:
        ctx.db.close_all()


def run_export(args) -> int:
    ctx = _context(args)
    try:
        artifact = ctx.artifacts_repo.get(args.artifact)
        if artifact is None:
            emit_error("NOT_FOUND", f"产物不存在：{args.artifact}", "先运行 merge 或从历史中选择产物")
            return 2
        options = ExportOptions(
            platform=args.platform,
            mode=args.mode,
            install_scope=args.install_scope,
            length_mode=args.length_mode,
            profile=args.profile,
            name_en=args.name_en,
            confirm_candidate=bool(args.confirm_candidate),
        )
        result = ctx.export_service.export(artifact, options)
        emit({"ok": True, "data": result})
        log(f"导出完成：{result.get('dir_path', '')}")
        return 0
    finally:
        ctx.db.close_all()


def run_validate(args) -> int:
    directory = os.path.abspath(args.artifact)
    manifest_path = os.path.join(directory, "manifest.json")
    skill_path = os.path.join(directory, "SKILL.md")
    if not os.path.isfile(manifest_path) or not os.path.isfile(skill_path):
        emit_error("INVALID_ARGUMENT", "不是有效产物目录", "传入含 SKILL.md 与 manifest.json 的目录")
        return 2
    registry = PlatformRegistry(paths.platforms_dir())
    entry = registry.entry(args.platform)
    if entry is None:
        emit_error("INVALID_ARGUMENT", f"平台规则不存在：{args.platform}", "先运行 platforms 查看平台 id")
        return 2
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as exc:
        emit_error("INVALID_ARGUMENT", "manifest.json 读取失败", str(exc))
        return 2
    rule = ExportService._export_rule(entry)
    document = read_document(skill_path)
    config, _warnings = load_config(args.data_dir or paths.data_dir())
    name = generate_name(
        rule,
        str(manifest.get("name", "")),
        args.name_en,
        document.frontmatter,
        "",
        config.slug_map,
    )
    description, level = rewrite_description(rule, document.description(), [], [], "")
    spec = prepare_spec(directory, rule, name, description, "dir")
    checks = run_preflight(rule, spec) + run_postflight(rule, spec)
    failed = errors(checks)
    emit(
        {
            "ok": not failed,
            "data": {
                "name": name,
                "description": description,
                "description_source": level,
                "checks": checks,
                "error_count": len(failed),
            },
        }
    )
    log(f"校验完成：{len(checks)} 项，error {len(failed)} 项")
    return 1 if failed else 0