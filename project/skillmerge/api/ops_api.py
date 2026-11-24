from __future__ import annotations

import os

from ..config.loader import save_config as persist_config
from ..services.ai_client import AIClient
from ..services.exporter.platform_registry.detail import build_detail
from ..services.exporter.platform_registry.query import query_platforms
from ..util.audit import read_audit, write_audit
from ..util.errors import DomainError
from ..util.logging import redact
from .platform_params import platform_params


def list_platforms(ctx, request):
    params = platform_params(request, ctx.registry)
    return 200, query_platforms(ctx.registry, params)


def get_platform(ctx, request):
    platform_id = request.params.get("id", "")
    records = ctx.registry.discovery_records()
    detail = build_detail(ctx.registry, platform_id, records)
    if detail is None:
        blocked = any(
            str(record.get("key")) == platform_id
            and (record.get("status") is None or int(record.get("status")) >= 400)
            for record in records
            if record.get("status") is None or str(record.get("status")).isdigit()
        )
        if blocked:
            raise DomainError(
                "PLATFORM_NOT_SELECTABLE",
                "该对象是不可达的探测记录，不是平台条目",
                "从平台清单选择可导出的条目",
                400,
            )
        raise DomainError("NOT_FOUND", f"平台不存在：{platform_id}", "从平台清单选择", 404)
    return 200, detail


def get_config(ctx, request):
    return 200, ctx.config.public()


def _apply_config(ctx, config) -> None:
    if isinstance(config, dict):
        values = config
    else:
        values = dict(vars(config))
    # Services keep a reference to this frozen config, so mutate in place instead of rebinding.
    for key, value in values.items():
        object.__setattr__(ctx.config, key, value)


def save_config(ctx, request):
    payload = request.json_data or {}
    if not isinstance(payload, dict):
        raise DomainError("INVALID_ARGUMENT", "配置必须是对象", "传入 JSON 对象", 400)
    config, warnings = persist_config(ctx.data_dir, payload)
    _apply_config(ctx, config)
    try:
        os.makedirs(ctx.config.save_dir, exist_ok=True)
    except OSError as exc:
        raise DomainError("STORAGE_ERROR", "保存目录不可写", f"更换 save_dir：{exc}", 400)
    write_audit(ctx.data_dir, "config", "config.json", "ok", {"keys": sorted(payload.keys())})
    return 200, {"config": ctx.config.public(), "warnings": warnings}


def list_audit(ctx, request):
    limit = request.q("limit", "100")
    try:
        value = max(1, min(500, int(limit)))
    except (TypeError, ValueError):
        raise DomainError("INVALID_ARGUMENT", "limit 必须是整数", "使用 1–500")
    return 200, {"items": read_audit(ctx.data_dir, value)}


def ai_test(ctx, request):
    ai = ctx.config.ai
    hint = {"api_key_set": bool(getattr(ai, "api_key", "")), "base_url_set": bool(ai.base_url), "model": ai.model}
    if not (ai.base_url and ai.model):
        return 200, {"reachable": False, "reason": "AI 未配置 base_url 或 model", **hint}
    client = AIClient(ai.base_url, ai.api_key, ai.model, timeout=10)
    try:
        client.ping()
    except Exception as exc:  # noqa: BLE001
        return 200, {"reachable": False, "reason": redact(str(exc))[:300], **hint}
    return 200, {"reachable": True, "reason": "", **hint}