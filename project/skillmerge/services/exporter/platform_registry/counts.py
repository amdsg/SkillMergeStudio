from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class RegistryCounts:
    total: int
    verified: int
    verified_official: int
    local_contract: int
    candidate: int
    unknown: int
    skill: int
    prompt: int

    def as_dict(self) -> Dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceCounts:
    evidence_total: int
    evidence_skill: int
    evidence_rules: int
    evidence_discovery: int
    no_evidence: int
    failed: int

    def as_dict(self) -> Dict[str, int]:
        return asdict(self)


def build_registry_counts(entries: Iterable[Any]) -> RegistryCounts:
    items = list(entries)
    verified = [item for item in items if item.verification_status == "verified"]
    official = [item for item in verified if item.source_type != "local_contract"]
    local = [item for item in verified if item.source_type == "local_contract"]
    candidate = [item for item in items if item.verification_status == "unknown"]
    return RegistryCounts(
        total=len(items),
        verified=len(verified),
        verified_official=len(official),
        local_contract=len(local),
        candidate=len(candidate),
        unknown=len(candidate),
        skill=sum(1 for item in items if item.kind == "skill"),
        prompt=sum(1 for item in items if item.kind == "prompt"),
    )


def build_evidence_counts(summary: Dict[str, Any]) -> EvidenceCounts:
    skill = int(summary.get("skill_md", 0))
    rules = int(summary.get("rules", 0))
    discovery = int(summary.get("discovery", 0))
    return EvidenceCounts(
        evidence_total=skill + rules + discovery,
        evidence_skill=skill,
        evidence_rules=rules,
        evidence_discovery=discovery,
        no_evidence=int(summary.get("no_evidence", 0)),
        failed=int(summary.get("failed", 0)),
    )


def registry_equations(counts: RegistryCounts) -> Dict[str, bool]:
    return {
        "total_eq_verified_candidate": counts.total == counts.verified + counts.candidate,
        "verified_eq_official_local": counts.verified == counts.verified_official + counts.local_contract,
        "unknown_eq_candidate": counts.unknown == counts.candidate,
        "total_eq_skill_prompt": counts.total == counts.skill + counts.prompt,
    }


def evidence_equations(counts: EvidenceCounts) -> Dict[str, bool]:
    return {
        "evidence_eq_parts": counts.evidence_total
        == counts.evidence_skill + counts.evidence_rules + counts.evidence_discovery,
    }


def all_equations(counts: RegistryCounts) -> bool:
    return all(registry_equations(counts).values())