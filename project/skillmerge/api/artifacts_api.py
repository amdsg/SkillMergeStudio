from __future__ import annotations

from typing import Any, Dict

from ..util.errors import DomainError
from .schemas import page_args
from ..services.history.ai_apply import apply_ai_suggestions
from ..services.history.history_service import artifacts_for_skill, detail, list_history
from ..services.history.undo import undo_artifact
from ..util.audit import write_audit


def history(ctx, request):
    limit, offset = page_args(request)
    platform = str(request.q("platform", "") or "").strip()
    return 200, list_history(ctx.artifacts_repo, limit, offset, ctx.skills_repo, platform)


def get_artifact(ctx, request):
    artifact = ctx.artifacts_repo.get(request.params.get("id", ""))
    if artifact is None:
        raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
    return 200, detail(ctx.artifacts_repo, artifact, ctx.skills_repo)


def undo(ctx, request):
    artifact = ctx.artifacts_repo.get(request.params.get("id", ""))
    if artifact is None:
        raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
    result = undo_artifact(ctx.artifacts_repo, artifact, ctx.config.save_dir)
    write_audit(ctx.data_dir, "undo", artifact.id, "ok", {"trash_path": result.get("trash_path", "")})
    return 200, result


def ai_apply(ctx, request):
    artifact = ctx.artifacts_repo.get(request.params.get("id", ""))
    if artifact is None:
        raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
    payload = request.json_data or {}
    keys = payload.get("keys") or []
    if not isinstance(keys, list):
        raise DomainError("INVALID_ARGUMENT", "keys 必须是数组", "传入已确认的章节 key 数组", 400)
    result = apply_ai_suggestions(ctx.artifacts_repo, artifact, keys)
    write_audit(
        ctx.data_dir,
        "merge",
        artifact.id,
        "ai-applied",
        {"keys": result.get("applied_keys", [])},
    )
    return 200, result


def rebuild(ctx, request):
    artifact = ctx.artifacts_repo.get(request.params.get("id", ""))
    if artifact is None:
        raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
    if artifact.status != "active":
        raise DomainError("NOT_FOUND", "产物不是 active 状态", "重新合并或选择其他产物", 404)
    payload = request.json_data or {}
    params = {
        "action": "rebuild",
        "artifact_id": artifact.id,
        "drop_missing_sources": bool(payload.get("drop_missing_sources", False)),
    }
    job_id = ctx.jobs.submit("merge", params)
    return 202, {"job_id": job_id, "status": "queued", "type": "rebuild"}


def skill_artifacts(ctx, request):
    return 200, artifacts_for_skill(ctx.artifacts_repo, request.params.get("id", ""))