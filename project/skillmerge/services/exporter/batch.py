from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Optional

from ...util.errors import CancelledError, DomainError
from .export_service import ExportOptions
from .platform_registry.format import format_info

MAX_BATCH_PLATFORMS = 28
UNSELECTABLE_EVIDENCE = ("failed_unreachable", "no_evidence", "discovery_source")


def dedupe_platforms(values: List[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def preflight_batch(registry, platforms: List[str], mode: str, confirm_candidate: bool) -> None:
    if not platforms:
        raise DomainError("EXPORT_BATCH_EMPTY", "至少选择一个平台", "选择 1–28 个平台后重试", 400)
    if len(platforms) > MAX_BATCH_PLATFORMS:
        raise DomainError(
            "EXPORT_BATCH_TOO_LARGE",
            "一次最多导出 %d 个平台" % MAX_BATCH_PLATFORMS,
            "减少平台数量后重试",
            400,
            {"max": MAX_BATCH_PLATFORMS, "requested": len(platforms)},
        )
    unknown: List[str] = []
    not_selectable: List[str] = []
    candidates: List[str] = []
    install_missing: List[str] = []
    for platform in platforms:
        entry = registry.entry(platform)
        if entry is None:
            unknown.append(platform)
            continue
        if entry.evidence_level in UNSELECTABLE_EVIDENCE:
            not_selectable.append(platform)
            continue
        info = format_info(entry)
        if entry.verification_status == "unknown" and not confirm_candidate:
            candidates.append(platform)
        if mode == "install" and not info["install_scopes"]:
            install_missing.append(platform)
    if unknown:
        raise DomainError(
            "EXPORT_PLATFORM_UNKNOWN",
            "存在未注册的平台",
            "从平台清单选择有效平台",
            400,
            {"platforms": unknown},
        )
    if not_selectable:
        raise DomainError(
            "PLATFORM_NOT_SELECTABLE",
            "存在不可导出的平台对象",
            "移除不可选对象后重试",
            400,
            {"platforms": not_selectable},
        )
    if candidates:
        raise DomainError(
            "PLATFORM_NOT_SELECTABLE",
            "候选平台规则未核验，需显式确认",
            "传入 confirm_candidate=true 后再导出",
            400,
            {"candidates": candidates},
        )
    if install_missing:
        raise DomainError(
            "EXPORT_INSTALL_UNAVAILABLE",
            "所选平台未配置安装目录",
            "改用 zip 或目录导出，或移除这些平台",
            466,
            {"platforms": install_missing},
        )


class ExportBatch:
    def __init__(self, service, registry) -> None:
        self.service = service
        self.registry = registry

    def _format(self, platform: str) -> Optional[Dict[str, Any]]:
        entry = self.registry.entry(platform)
        return format_info(entry) if entry is not None else None

    def _label(self, platform: str) -> str:
        entry = self.registry.entry(platform)
        return entry.label if entry is not None else platform

    def _success(self, platform: str, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "platform": platform,
            "label": self._label(platform),
            "kind": result.get("kind"),
            "status": "succeeded",
            "artifact_id": result.get("artifact_id"),
            "dir_path": result.get("dir_path"),
            "zip_path": result.get("zip_path"),
            "installed_path": result.get("installed_path"),
            "size_bytes": result.get("size_bytes"),
            "sha256": result.get("sha256"),
            "sources_count": result.get("sources_count"),
            "download_url": result.get("download_url"),
            "format": self._format(platform),
            "error": None,
        }

    def _failed(self, platform: str, exc: DomainError) -> Dict[str, Any]:
        return {
            "platform": platform,
            "label": self._label(platform),
            "kind": None,
            "status": "failed",
            "artifact_id": None,
            "dir_path": None,
            "zip_path": None,
            "installed_path": None,
            "size_bytes": None,
            "sha256": None,
            "sources_count": None,
            "download_url": None,
            "format": self._format(platform),
            "error": {
                "code": exc.code,
                "message": exc.message,
                "fix": exc.fix,
                "checks": list(exc.details.get("checks", [])),
            },
        }

    def _cancelled(self, platform: str) -> Dict[str, Any]:
        return {
            "platform": platform,
            "label": self._label(platform),
            "kind": None,
            "status": "cancelled",
            "artifact_id": None,
            "dir_path": None,
            "zip_path": None,
            "installed_path": None,
            "size_bytes": None,
            "sha256": None,
            "sources_count": None,
            "download_url": None,
            "format": self._format(platform),
            "error": None,
        }

    def run(
        self,
        artifact,
        platforms: List[str],
        base_options: ExportOptions,
        job_id: str = "",
        cancel_token=None,
        progress=None,
    ) -> Dict[str, Any]:
        total = len(platforms)
        items: List[Dict[str, Any]] = []
        cancelled = False
        for index, platform in enumerate(platforms, 1):
            label = self._label(platform)
            if cancelled or (cancel_token is not None and cancel_token.is_set()):
                cancelled = True
                items.append(self._cancelled(platform))
                continue
            if progress:
                progress("export", index, total, "已处理 %d/%d · %s" % (index, total, label))
            options = replace(base_options, platform=platform)
            try:
                result = self.service.export(
                    artifact,
                    options,
                    job_id=job_id,
                    cancel_token=cancel_token,
                    progress=progress,
                )
                items.append(self._success(platform, result))
            except CancelledError:
                cancelled = True
                items.append(self._cancelled(platform))
            except DomainError as exc:
                items.append(self._failed(platform, exc))
        summary = {
            "total": total,
            "succeeded": sum(1 for item in items if item["status"] == "succeeded"),
            "failed": sum(1 for item in items if item["status"] == "failed"),
            "cancelled": sum(1 for item in items if item["status"] == "cancelled"),
        }
        payload: Dict[str, Any] = {
            "batch": True,
            "source_artifact_id": artifact.id,
            "items": items,
            "summary": summary,
        }
        if cancelled:
            payload["cancelled"] = True
        return payload