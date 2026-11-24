from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .counts import EvidenceCounts, RegistryCounts, evidence_equations, registry_equations


def _diag(code: str, severity: str, message: str, files: List[str], fix: str, items: List[Any] = None) -> Dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "files": files,
        "fix": fix,
        "items": items or [],
    }


def diagnose(counts: RegistryCounts, entries: Iterable[Any], evidence: EvidenceCounts = None) -> List[Dict[str, Any]]:
    diagnostics = []
    equations = registry_equations(counts)
    if not equations["total_eq_verified_candidate"]:
        diagnostics.append(_diag("COUNTS_MISMATCH_TOTAL", "error", "total ≠ verified + candidate", [], "检查条目状态"))
    if not equations["verified_eq_official_local"]:
        diagnostics.append(_diag("COUNTS_MISMATCH_VERIFIED", "error", "verified ≠ official + local_contract", [], "检查 source_type"))
    if not equations["unknown_eq_candidate"]:
        diagnostics.append(_diag("COUNTS_UNKNOWN_ALIAS", "error", "unknown ≠ candidate", [], "检查状态映射"))
    if not equations["total_eq_skill_prompt"]:
        diagnostics.append(_diag("COUNTS_KIND_SUM", "error", "total ≠ skill + prompt", [], "检查 kind"))
    legacy_files = [str(item.id) for item in entries if getattr(item, "legacy_limits", None)]
    if legacy_files:
        diagnostics.append(
            _diag("LEGACY_LIMITS_PRESENT", "warn", "存在 v1 legacy_limits", legacy_files, "仅展示，不参与 preflight")
        )
    candidate_with_body = [str(item.id) for item in entries if item.verification_status == "unknown" and item.rule_body]
    if candidate_with_body:
        diagnostics.append(
            _diag("CANDIDATE_HAS_LIMITS", "error", "candidate 仍带规则体", candidate_with_body, "规则体必须为 null")
        )
    if evidence is not None and not evidence_equations(evidence)["evidence_eq_parts"]:
        diagnostics.append(_diag("EVIDENCE_SUM", "error", "evidence_total ≠ skill + rules + discovery", [], "重算汇总"))
    if evidence is None:
        diagnostics.append(_diag("DISCOVERY_MISSING", "warn", "本轮无探测记录", [], "运行 validate_discovery.py 或忽略"))
    return diagnostics