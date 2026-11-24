#!/usr/bin/env python3
"""Aggregate gate runner. Any failing gate makes the run fail."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

WB_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = WB_ROOT.parent
GATES = (
    ("adapter_registry", ["skill-workbench/tools/check_adapter_registry.py", "--check", "--assert-counts", "--assert-groups", "--assert-evidence"]),
    ("target_registry_open", ["skill-workbench/tools/check_target_registry_open.py", "--check"]),
    ("tool_match", ["skill-workbench/tools/check_tool_match.py", "--check"]),
    ("applicability", ["skill-workbench/tools/check_applicability.py", "--check"]),
    ("inheritance", ["skill-workbench/tools/check_inheritance.py", "--check", "--scan-root", "."]),
    ("i18n", ["skill-workbench/tools/check_i18n_wb.py", "--check", "--assert-screens"]),
    ("defaults", ["skill-workbench/tools/check_wb_defaults.py", "--check"]),
    ("no_third_party", ["skill-workbench/tools/check_no_third_party_wb.py", "--check", "--root", "skill-workbench"]),
    ("tutorial_no_write", ["skill-workbench/tools/check_tutorial_no_write.py", "--check"]),
)


def run_gate(name: str, command: list[str]) -> dict:
    started = time.time()
    proc = subprocess.run([sys.executable, *command], cwd=str(PROJECT_ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return {
        "name": name,
        "command": " ".join(command),
        "exit_code": proc.returncode,
        "seconds": round(time.time() - started, 3),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="run all workbench gates")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--only", default="")
    parser.add_argument("--report", default="")
    args = parser.parse_args(argv)
    selected = [entry for entry in GATES if not args.only or entry[0] == args.only]
    if not selected:
        print(f"WB-GATE: unknown gate {args.only}", file=sys.stderr)
        return 2
    results = [run_gate(name, command) for name, command in selected]
    failed = [result for result in results if result["exit_code"] != 0]
    for result in results:
        print(f"WB-GATE[{result['name']}]: exit={result['exit_code']} {result['seconds']}s")
        if result["exit_code"] != 0:
            if result["stderr"]:
                sys.stderr.write(result["stderr"])
            if result["stdout"]:
                sys.stderr.write(result["stdout"])
    summary = {
        "total": len(results),
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "failed_names": [result["name"] for result in failed],
        "results": results,
    }
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"WB-GATE: total={summary['total']} passed={summary['passed']} failed={summary['failed']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())