from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {"merger": 0.85, "exporter": 0.85, "scanner": 0.85}
OVERALL = 0.75


def _normal(name: str) -> str:
    return name.replace("\\", "/")


def main() -> int:
    path = ROOT / "coverage.json"
    if not path.is_file():
        print("未找到 coverage.json。先运行：python -m pytest -q --cov=skillmerge --cov-report=json", file=sys.stderr)
        return 2
    data = json.loads(path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    overall = float(totals.get("percent_covered", 0) or 0) / 100.0
    issues = []
    if overall < OVERALL:
        issues.append(f"整体覆盖率 {overall:.1%}，低于 {OVERALL:.0%}")
    files = data.get("files", {})
    for group, threshold in TARGETS.items():
        covered = 0
        statements = 0
        for name, payload in files.items():
            if f"skillmerge/services/{group}/" not in _normal(name):
                continue
            summary = payload.get("summary", {})
            covered += int(summary.get("covered_lines", 0) or 0)
            statements += int(summary.get("num_statements", 0) or 0)
        rate = (covered / statements) if statements else 0.0
        if rate < threshold:
            issues.append(f"services/{group} 覆盖率 {rate:.1%}，低于 {threshold:.0%}")
    if issues:
        print("覆盖率门禁失败：", file=sys.stderr)
        for issue in issues:
            print(" - " + issue, file=sys.stderr)
        return 1
    print(f"覆盖率门禁通过（整体 {overall:.1%}；merger/exporter/scanner ≥85%）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())