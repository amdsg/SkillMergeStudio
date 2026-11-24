#!/usr/bin/env python3
"""Intermediate schema gate: eight parts, neutral fields, no bypass."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WB = ROOT
SCHEMA = WB / "agent" / "adapters" / "intermediate_schema.json"
AGENT = WB / "agent"
REQUIRED = ("schema_version", "identity", "intent", "capabilities", "instructions", "examples", "resources", "provenance")
PREFIXES = ("claude_", "openai_", "gpt_", "doubao_", "deepseek_", "qwen_", "kimi_")
WORDS = ("官方兼容", "已适配", "official compatible")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="intermediate schema gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--assert-no-bypass", action="store_true")
    parser.add_argument("--assert-merge-outputs", action="store_true")
    args = parser.parse_args(argv)
    errors = []
    if not SCHEMA.is_file():
        print("E_INTERMEDIATE_INVALID: schema missing", file=sys.stderr)
        return 2
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    if not isinstance(schema.get("schema_version"), int):
        errors.append("schema_version must be integer")
    if tuple(schema.get("required_keys") or ()) != REQUIRED:
        errors.append(f"required_keys mismatch: {schema.get('required_keys')}")
    forbidden = schema.get("forbidden_field_names") or []
    for prefix in PREFIXES:
        if not any(pattern.startswith("^" + prefix) for pattern in forbidden):
            errors.append(f"forbidden_field_names missing {prefix}")
    if not schema.get("forbidden_value_patterns"):
        errors.append("forbidden_value_patterns empty")
    if "product_version" in SCHEMA.read_text(encoding="utf-8"):
        errors.append("schema must not carry product_version")
    for path in list(AGENT.rglob("*.py")):
        if path.name == "intermediate.py":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for word in WORDS:
            if word in text:
                errors.append(f"{path.relative_to(WB).as_posix()}: wording {word}")
        if args.assert_no_bypass or True:
            for number, line in enumerate(text.splitlines(), 1):
                if "_head(" in line:
                    errors.append(f"{path.relative_to(WB).as_posix()}:{number}: legacy header bypass")
                if "write_text(" in line and ("head" in line or "prefix" in line):
                    errors.append(f"{path.relative_to(WB).as_posix()}:{number}: direct header write")
    if args.assert_merge_outputs:
        # Reserved for T-45; behaviour is unchanged until merge outputs exist.
        pass
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-INTERMEDIATE: parts={len(schema.get('required_keys') or [])} errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())