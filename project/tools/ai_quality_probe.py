#!/usr/bin/env python3
"""真实 AI 端点质量抽样（M6 / T6-03）。默认 blocked，不伪造结论。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from skillmerge.config import paths
from skillmerge.config.loader import load_config

SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
)
RULES = (
    (re.compile(r"C:\\Users\\[^\\\s]+"), "<home>"),
    (re.compile(r"/home/[^/\s]+"), "<home>"),
    (SECRET_PATTERNS[0], "<secret>"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._-]{8,}"), "Bearer <secret>"),
    (SECRET_PATTERNS[2], "<secret>"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<email>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<ip>"),
    (re.compile(r"https?://[^\s\"']+"), "<url>"),
    (re.compile(r"[A-Za-z]:\\[^\s\"']+"), "<path>"),
)


class Budget:
    def __init__(self, limit: int) -> None:
        self.limit = int(limit or 0)
        self.used = 0
        self.stopped_reason = ""

    def add(self, tokens: int) -> bool:
        self.used += int(tokens or 0)
        if self.limit and self.used > self.limit:
            self.stopped_reason = "budget_exhausted"
            return False
        return True


def sanitize(text: str):
    applied = []
    replacements = 0
    value = str(text)
    for pattern, replacement in RULES:
        value, count = pattern.subn(replacement, value)
        if count:
            applied.append(pattern.pattern)
            replacements += count
    if any(pattern.search(value) for pattern in SECRET_PATTERNS):
        raise ValueError("M6-SANITIZE-LEAK")
    return value, applied, replacements


def gate(config, key_env: str, sample_dir: str, budget: int):
    ai = config.ai
    missing = []
    if not (ai.enabled and ai.base_url and ai.model):
        missing.append("missing_endpoint")
    key = os.environ.get(key_env, "")
    if not key:
        missing.append("missing_auth")
    if not sample_dir or not os.path.isdir(sample_dir):
        missing.append("missing_samples")
    if not budget or int(budget) <= 0:
        missing.append("missing_budget_auth")
    return ("blocked" if missing else "authorized"), missing, key


def rerun_compare(current: dict, previous: dict, tolerance=None) -> dict:
    if tolerance is None:
        return {"verdict": "cannot-judge", "tolerance": None, "note": "容差未确认"}
    diff = abs(float(current.get("agreement_rate", 0)) - float(previous.get("agreement_rate", 0)))
    return {"verdict": "stable" if diff <= float(tolerance) else "unstable", "tolerance": tolerance, "diff": diff}


def base_report(config, key: str, args) -> dict:
    ai = config.ai
    host = ""
    if ai.base_url:
        host = re.sub(r"https?://", "", ai.base_url).split("/")[0]
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "ai_quality_probe",
        "endpoint": {"host": host, "model": ai.model, "provider": "openai-compatible"},
        "key_fingerprint": hashlib.sha256(key.encode("utf-8")).hexdigest()[:8] if key else "",
        "sanitize": {"rules_applied": [], "replacements": 0},
        "budget": {"limit": int(args.budget_tokens or 0), "used": 0, "stopped_reason": "", "estimated": True},
        "paths": {
            "classify": {"samples": int(args.samples)},
            "merge": {"sets": int(args.merge_sets)},
            "fallback": {"all_expected": False},
        },
        "thresholds": {"confirmed": False, "source": ""},
        "conclusion": "distribution-only",
        "result": "blocked",
        "missing": [],
        "notes": [],
    }


def write_report(path: Path, payload: dict, force: bool) -> int:
    if path.exists() and not force:
        print(f"M6-REPORT-EXISTS: {path}（使用 --force 覆盖）", file=sys.stderr)
        return 1
    if "simulated" not in path.name:
        print("M6-SIM-LEAK: 模拟/干跑只能写文件名含 simulated 的报告", file=sys.stderr)
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="AI 质量抽样（默认 blocked）")
    parser.add_argument("--config", default="")
    parser.add_argument("--key-env", default="SKILLMERGE_API_KEY")
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument("--merge-sets", type=int, default=3)
    parser.add_argument("--sample-dir", default="")
    parser.add_argument("--budget-tokens", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--out", default="")
    parser.add_argument("--rerun", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    data_dir = args.config or paths.data_dir()
    config, _warnings = load_config(data_dir)
    state, missing, key = gate(config, args.key_env, args.sample_dir, args.budget_tokens)
    payload = base_report(config, key, args)
    payload["missing"] = missing

    if args.rerun:
        try:
            previous = json.loads(Path(args.rerun).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print(f"M6-INPUT-MISSING: {exc}", file=sys.stderr)
            return 2
        payload["paths"]["rerun"] = rerun_compare(payload, previous, tolerance=None)
        payload["result"] = "blocked"
        payload["notes"].append("容差未确认，结论只能是 cannot-judge")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.sample_dir:
        candidates = [p for p in Path(args.sample_dir).rglob("*.md")][:2]
        for path in candidates:
            try:
                sanitize(path.read_text(encoding="utf-8", errors="replace"))
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                payload["result"] = "blocked"
                payload["missing"] = ["sanitize_leak"]
                print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                return 0

    if state == "authorized" and not args.dry_run:
        payload["result"] = "blocked"
        payload["missing"] = ["sampling_not_implemented"]
        payload["notes"].append("T6-03c 仅在 Q-33 提供端点/样本/预算后启用；不得用桩响应代跑")
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    if args.out:
        target = Path(args.out)
        if "simulated" not in target.name:
            print("M6-SIM-LEAK: 干跑/未授权状态不得写真实质量报告", file=sys.stderr)
            return 1
        code = write_report(target, payload, args.force)
        if code:
            return code
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())