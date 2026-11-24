from __future__ import annotations

from ..services.exporter.export_service import ExportOptions
from ..services.exporter.preview import export_preview
from ..util.errors import DomainError
from .schemas import export_preview_params


def preview(ctx, request):
    params = export_preview_params(request.json_data or {})
    artifact = ctx.artifacts_repo.get(params["artifact_id"])
    if artifact is None:
        raise DomainError("NOT_FOUND", "产物不存在", "刷新历史列表后重试", 404)
    if artifact.status != "active":
        raise DomainError("EXPORT_BLOCKED", "产物不是 active 状态", "重新合并或选择其他产物", 466)
    platforms = params["platforms"] or [params["platform"]]
    values = dict(params)
    values.pop("artifact_id", None)
    values.pop("platforms", None)
    options = ExportOptions(**values)
    return 200, export_preview(ctx.export_service, artifact, platforms, options)