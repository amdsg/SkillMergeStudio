#!/usr/bin/env python3
"""Applicability gate: three states, no inference from description/topics."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APPLICABILITY = ROOT / "agent" / "adapters" / "applicability.json"
CORE = ROOT / "agent" / "core" / "applicability.py"
ENUMS = ROOT / "extension" / "i18n-enums.json"
FORBIDDEN_INFERENCE = ("description", "topics")


def load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="applicability gate")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    errors = []
    data = load(APPLICABILITY, None)
    if not isinstance(data, dict):
        errors.append("WB-APP-1 applicability.json missing")
    else:
        for field in ("source_files", "field_names"):
            if not isinstance(data.get(field), list):
                errors.append(f"WB-APP-1 {field} must be a list")
        if data.get("status") == "unregistered" and (data.get("source_files") or data.get("field_names")):
            errors.append("WB-APP-1 unregistered status must not list fields")
    if not CORE.is_file():
        errors.append("WB-APP-2 agent/core/applicability.py missing")
    else:
        text = CORE.read_text(encoding="utf-8", errors="replace")
        for state in ("universal", "model_specific", "unknown"):
            if state not in text:
                errors.append(f"WB-APP-2 missing state {state}")
        for token in FORBIDDEN_INFERENCE:
            if token in text:
                errors.append(f"WB-APP-3 applicability must not infer from {token}")
        if "E_APPLICABILITY_ACK_REQUIRED" not in text:
            errors.append("WB-APP-2 missing ack error code")
    enums = load(ENUMS, {})
    labels = enums.get("applicability", {}) if isinstance(enums, dict) else {}
    for state in ("universal", "model_specific", "unknown"):
        if state not in labels:
            errors.append(f"WB-APP-4 missing i18n enum {state}")
    unknown = labels.get("unknown", {}) if isinstance(labels, dict) else {}
    if unknown:
        text = json.dumps(unknown, ensure_ascii=False)
        if "通用" in text or "不兼容" in text:
            errors.append("WB-APP-5 unknown state must not say universal or incompatible")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-APP: errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())