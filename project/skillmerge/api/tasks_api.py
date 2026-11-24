from __future__ import annotations

from ..util.errors import DomainError
from ..services.exporter.batch import preflight_batch
from ..services.exporter.manifest import resolve_download
from ..services.merger.merge_service import MergeOptions
from .schemas import classify_params, export_params, merge_params, scan_params


def post_scan(ctx, request):
    params = scan_params(request.json_data or {}, ctx.config, full=False)
    job_id = ctx.jobs.submit("scan", params)
    return 202, {"job_id": job_id, "status": "queued"}


def post_scan_all(ctx, request):
    params = scan_params(request.json_data or {}, ctx.config, full=True)
    job_id = ctx.jobs.submit("full_scan", params)
    return 202, {"job_id": job_id, "status": "queued"}


def post_classify(ctx, request):
    params = classify_params(request.json_data or {})
    job_id = ctx.jobs.submit("classify", params)
    return 202, {"job_id": job_id, "status": "queued", "type": "classify"}


def get_config(ctx, request):
    return 200, ctx.config.public()


def get_platforms(ctx, request):
    items = ctx.registry.public()
    return 200, {"items": items, "total": len(items)}


def _skills(ctx, source_ids):
    skills = []
    for skill_id in source_ids:
        skill = ctx.skills_repo.get(skill_id)
        if skill is None:
            raise DomainError("NOT_FOUND", f"技能不存在：{skill_id}", "重新扫描后刷新列表", 404)
        skills.append(skill)
    return skills


def _options(params):
    values = dict(params)
    values.pop("sources", None)
    return MergeOptions(**values)


def post_preview(ctx, request):
    params = merge_params(request.json_data or {}, ctx.config)
    skills = _skills(ctx, params["sources"])
    missing = [skill.name or skill.id for skill in skills if skill.missing]
    if missing:
        raise DomainError("MERGE_SOURCE_MISSING", "存在已缺失的源技能", "移除失效源后重试", 400)
    preview = ctx.merge_service.preview(skills, _options(params))
    return 200, preview


def post_merge(ctx, request):
    params = merge_params(request.json_data or {}, ctx.config)
    skills = _skills(ctx, params["sources"])
    missing = [skill.name or skill.id for skill in skills if skill.missing]
    if missing:
        raise DomainError("MERGE_SOURCE_MISSING", "存在已缺失的源技能", "移除失效源后重试", 400)
    job_id = ctx.jobs.submit("merge", params)
    return 202, {"job_id": job_id, "status": "queued", "type": "merge"}


def post_export(ctx, request):
    params = export_params(request.json_data or {})
    artifact = ctx.artifacts_repo.get(params["artifact_id"])
    if artifact is None:
        raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
    if artifact.status != "active":
        raise DomainError("EXPORT_BLOCKED", "产物不是 active 状态", "重新合并或选择其他产物", 466)
    platforms = params.get("platforms") or []
    if platforms:
        preflight_batch(ctx.registry, platforms, params["mode"], params["confirm_candidate"])
        job_id = ctx.jobs.submit("export", params)
        return 202, {
            "job_id": job_id,
            "status": "queued",
            "type": "export",
            "batch": True,
            "platforms": platforms,
        }
    ctx.registry.require(params["platform"])
    job_id = ctx.jobs.submit("export", params)
    return 202, {"job_id": job_id, "status": "queued", "type": "export"}


def download_artifact(ctx, request):
    artifact = ctx.artifacts_repo.get(request.params.get("id", ""))
    if artifact is None:
        raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
    return resolve_download(artifact, request.q("path", ""))