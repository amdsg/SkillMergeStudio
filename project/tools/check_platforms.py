from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from skillmerge.services.exporter.platform_registry.counts import registry_equations
from skillmerge.services.exporter.registry import PlatformRegistry


def main() -> int:
    registry = PlatformRegistry(os.path.join(ROOT, "platforms"))
    schema = registry.result.schema
    counts = registry.counts()
    issues = []
    if schema.get("schema_version") != 2:
        issues.append("schema_version != 2")
    for name, ok in registry_equations(counts).items():
        if not ok:
            issues.append(f"counts 等式失败：{name}")
    ids = {entry.id for entry in registry.entries()}
    missing = [item for item in schema["baseline_ids"] if item not in ids]
    if missing:
        issues.append(f"基线 id 缺失：{missing}")
    for entry in registry.entries():
        if entry.verification_status == "unknown" and entry.rule_body:
            issues.append(f"{entry.id}: candidate 仍带规则体")
        if entry.verification_status == "unknown" and entry.legacy_limits and entry.origin != "baseline":
            issues.append(f"{entry.id}: legacy_limits 非基线")
        if entry.verification_status == "verified" and (not entry.source or not entry.verified_at):
            issues.append(f"{entry.id}: verified 缺 source/verified_at")
        if entry.evidence_level in schema.get("forbid_in_registry", []):
            issues.append(f"{entry.id}: 使用了禁止的证据级别")
    for diagnostic in registry.diagnostics():
        if diagnostic.get("severity") == "error":
            issues.append(f"诊断 {diagnostic['code']}: {diagnostic['message']}")
    evidence = registry.evidence()
    if evidence:
        equations = evidence.get("equations") or {}
        if not all(equations.values()):
            issues.append("探测记录计数等式失败")
    print(
        json.dumps(
            {
                "ok": not issues,
                "counts": counts.as_dict(),
                "evidence": {
                    "probed": evidence.get("probed") if evidence else None,
                    "skill_md": evidence.get("skill_md") if evidence else None,
                    "rules": evidence.get("rules") if evidence else None,
                    "discovery": evidence.get("discovery") if evidence else None,
                },
                "issues": issues,
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())