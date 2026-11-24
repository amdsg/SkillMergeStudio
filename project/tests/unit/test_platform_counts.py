from __future__ import annotations

from types import SimpleNamespace

from skillmerge.services.exporter.platform_registry.counts import (
    EvidenceCounts,
    RegistryCounts,
    build_evidence_counts,
    build_registry_counts,
    evidence_equations,
    registry_equations,
)


def entry(platform_id, kind="skill", status="unknown", source_type="official_docs"):
    return SimpleNamespace(id=platform_id, kind=kind, verification_status=status, source_type=source_type)


def test_registry_counts_and_equations():
    entries = [
        entry("official", status="verified", source_type="official_docs"),
        entry("local", status="verified", source_type="local_contract"),
        entry("candidate", status="unknown"),
        entry("prompt", kind="prompt", status="unknown"),
    ]
    counts = build_registry_counts(entries)
    assert counts == RegistryCounts(4, 2, 1, 1, 2, 2, 3, 1)
    assert all(registry_equations(counts).values())


def test_one_status_change_only_moves_status_fields():
    base = [
        entry("a", status="verified", source_type="official_docs"),
        entry("b", status="unknown"),
        entry("c", status="unknown"),
    ]
    before = build_registry_counts(base)
    changed = build_registry_counts(
        [entry("a", status="unknown"), entry("b", status="unknown"), entry("c", status="unknown")]
    )
    assert before.verified == 1 and before.candidate == 2
    assert changed.verified == 0 and changed.candidate == 3
    assert before.skill == changed.skill == 3
    assert before.prompt == changed.prompt == 0


def test_evidence_counts_and_separation():
    evidence = build_evidence_counts(
        {"skill_md": 14, "rules": 21, "discovery": 1, "no_evidence": 13, "failed": 28}
    )
    assert evidence == EvidenceCounts(36, 14, 21, 1, 13, 28)
    assert all(evidence_equations(evidence).values())
    assert not isinstance(evidence, RegistryCounts)
    assert not issubclass(EvidenceCounts, RegistryCounts)
    assert not issubclass(RegistryCounts, EvidenceCounts)