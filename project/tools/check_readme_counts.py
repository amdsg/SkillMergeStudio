#!/usr/bin/env python3
"""README 数字与规格基线一致性校验（只读）。"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / ".codeartsdoer/specs/skill_workbench/spec.md"
README = ROOT / "README.txt"

REQ_RE = re.compile(r"^\s*(?:\d+\.\s+|-\s+)\*\*(REQ-WB-[A-Z0-9]+-\d{3})\*\*\s*\[(P[012])\]", re.M)
README_COUNT_RE = re.compile(r"（(\d+) 条；P0 (\d+) / P1 (\d+) / P2 (\d+)）")
FORBIDDEN = (
    (re.compile(r"361\s*条[^\n。]{0,12}(?:全部|均|逐条)?[^\n。]{0,6}(?:通过|已验证)"), "361-count-claim"),
    (re.compile(r"已继承\s*189\s*条"), "inheritance-claim"),
    (re.compile(r"支持\s*25\s*个\s*(?:平台|模型|目标)"), "target-total-claim"),
)
NEGATION = re.compile(r"不得|禁止|未|不|无法|不可|没有|cannot|not", re.I)


def spec_counts() -> dict:
    text = SPEC.read_text(encoding="utf-8")
    entries = REQ_RE.findall(text)
    counts = {"total": len(entries), "P0": 0, "P1": 0, "P2": 0}
    for _, prio in entries:
        counts[prio] += 1
    counts["unique"] = len({req for req, _ in entries})
    return counts


def check_readme(counts: dict) -> list:
    issues = []
    text = README.read_text(encoding="utf-8", errors="replace")
    match = README_COUNT_RE.search(text)
    expected = (counts["total"], counts["P0"], counts["P1"], counts["P2"])
    if not match:
        issues.append(f"README-TOTAL-MISSING: expected {expected}")
    else:
        actual = tuple(int(group) for group in match.groups())
        if actual != expected:
            issues.append(f"README-TOTAL-MISMATCH: expected {expected} actual {actual}")
    if counts["unique"] != counts["total"]:
        issues.append(f"SPEC-ID-DUPLICATE: total {counts['total']} unique {counts['unique']}")
    for number, line in enumerate(text.splitlines(), 1):
        for pattern, label in FORBIDDEN:
            for match in pattern.finditer(line):
                window = line[max(0, match.start() - 14): match.end() + 14]
                if NEGATION.search(window):
                    continue
                issues.append(f"README-WORDING[{label}]: README.txt:{number}")
    return issues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="README 数字一致性校验")
    parser.add_argument("--check", action="store_true")
    parser.parse_args(argv)
    if not SPEC.is_file():
        print("README-CHECK: spec.md missing", file=sys.stderr)
        return 2
    if not README.is_file():
        print("README-CHECK: README.txt missing", file=sys.stderr)
        return 2
    counts = spec_counts()
    issues = check_readme(counts)
    for item in issues:
        print(item, file=sys.stderr)
    print(
        f"README-CHECK: total={counts['total']} P0={counts['P0']} P1={counts['P1']} "
        f"P2={counts['P2']} issues={len(issues)}"
    )
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())