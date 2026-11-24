from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from skillmerge.services.exporter.platform_registry.discovery_reader import grade, load_latest, load_round


def _summary_path(source_file: str, round_name: str) -> str:
    return os.path.join(os.path.dirname(source_file), f"summary-{round_name}.json")


def _build(result, source_file: str) -> Dict[str, Any]:
    payload = dict(result.summary or {})
    payload["source_file"] = os.path.basename(source_file)
    payload["issues"] = result.issues
    return payload


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="grade_evidence.py")
    parser.add_argument("--file", default="")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.file:
        source_file = os.path.abspath(args.file)
        result = load_round(source_file)
    else:
        directory = os.path.join(ROOT, "platforms", "discovery")
        result = load_latest(directory)
        source_file = os.path.join(directory, f"{result.round_name}.json") if result else ""
    if result is None or not result.summary:
        print(json.dumps({"ok": False, "error": "没有可用的探测记录"}, ensure_ascii=False))
        return 1
    payload = _build(result, source_file)
    target = _summary_path(source_file, result.round_name)
    if args.write:
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
        print(f"written {target}")
    if args.check:
        if not os.path.isfile(target):
            print(json.dumps({"ok": False, "error": "summary 不存在"}, ensure_ascii=False))
            return 1
        try:
            existing = json.load(open(target, encoding="utf-8"))
        except (OSError, ValueError):
            print(json.dumps({"ok": False, "error": "summary 损坏"}, ensure_ascii=False))
            return 1
        if existing != payload:
            print(json.dumps({"ok": False, "error": "summary 与重算结果不一致"}, ensure_ascii=False))
            return 1
    print(
        json.dumps(
            {
                "ok": True,
                "round": result.round_name,
                "probed": payload.get("probed"),
                "ok_pages": payload.get("ok"),
                "failed": payload.get("failed"),
                "skill_md": payload.get("skill_md"),
                "rules": payload.get("rules"),
                "discovery": payload.get("discovery"),
                "no_evidence": payload.get("no_evidence"),
                "by_level": payload.get("by_level"),
                "summary_path": target,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())