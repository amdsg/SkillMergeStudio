from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...util.errors import DomainError
from .platform_registry.counts import EvidenceCounts, RegistryCounts
from .platform_registry.loader import PlatformEntry, PlatformLoadResult, load_registry


class PlatformRegistry:
    def __init__(self, directory: str) -> None:
        self.directory = directory
        self._result: Optional[PlatformLoadResult] = None
        self.reload()

    def reload(self) -> None:
        self._result = load_registry(self.directory)

    @property
    def result(self) -> PlatformLoadResult:
        if self._result is None:
            self.reload()
        return self._result

    def entries(self) -> List[PlatformEntry]:
        return list(self.result.entries)

    def entry(self, platform_id: str) -> Optional[PlatformEntry]:
        return self.result.entry(platform_id)

    def counts(self) -> RegistryCounts:
        return self.result.counts

    def evidence(self) -> Optional[Dict[str, Any]]:
        return self.result.evidence

    def evidence_counts(self) -> Optional[EvidenceCounts]:
        evidence = self.evidence()
        if not evidence:
            return None
        from .platform_registry.counts import build_evidence_counts

        return build_evidence_counts(evidence)

    def diagnostics(self) -> List[Dict[str, Any]]:
        return list(self.result.diagnostics)

    def discovery_records(self) -> List[Dict[str, Any]]:
        return list(self.result.records)

    def get(self, platform_id: str) -> Optional[Dict[str, Any]]:
        entry = self.entry(platform_id)
        return entry.as_rule() if entry else None

    def require(self, platform_id: str) -> Dict[str, Any]:
        rule = self.get(platform_id)
        if rule is None:
            raise DomainError("INVALID_ARGUMENT", f"平台规则不存在：{platform_id}", "选择已注册的平台或 generic", 400)
        return rule

    def public(self) -> List[Dict[str, Any]]:
        return [entry.as_public() for entry in self.entries()]

    def public_entries(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": entry.id,
                "label": entry.label,
                "kind": entry.kind,
                "group": entry.group,
                "origin": entry.origin,
                "batch": entry.batch,
                "source": entry.source,
                "source_type": entry.source_type,
                "verification_status": entry.verification_status,
                "evidence_level": entry.evidence_level,
                "verified_at": entry.verified_at,
                "last_verified_at": entry.last_verified_at,
                "unknown_fields": list(entry.unknown_fields),
                "notes": entry.notes,
                "aliases": list(entry.aliases),
                "legacy_limits_present": entry.legacy_limits is not None,
            }
            for entry in self.entries()
        ]