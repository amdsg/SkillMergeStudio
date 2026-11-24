#!/usr/bin/env python3
"""Render template gate: registry binding, evidence, changelog, no limit values."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WB = ROOT
TEMPLATES = WB / "agent" / "adapters" / "templates"
TARGETS = WB / "agent" / "adapters" / "targets.json"
CHANGELOG = TEMPLATES / "CHANGELOG.json"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="render template gate")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--assert-changelog", action="store_true")
    parser.add_argument("--assert-evidence", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(WB))
    from agent.core import render  # noqa: E402

    errors = []
    registry = json.loads((TEMPLATES / "_registry.json").read_text(encoding="utf-8"))
    targets = {item["id"]: item for item in json.loads(TARGETS.read_text(encoding="utf-8"))}
    seen = set()
    for entry in registry.get("templates", []):
        template_id = entry.get("template_id")
        target_id = entry.get("target_id")
        if template_id in seen:
            errors.append(f"duplicate template_id {template_id}")
        seen.add(template_id)
        if target_id != "*" and target_id not in targets:
            errors.append(f"template {template_id} bound to unknown target {target_id}")
        template = json.loads((TEMPLATES / entry["file"]).read_text(encoding="utf-8"))
        errors.extend(f"{template_id}: {error}" for error in render.validate_template(template))
        if args.assert_evidence and target_id != "*" and targets.get(target_id, {}).get("evidence_level") == "unknown":
            errors.append(f"{template_id}: dedicated template for unknown target")
    changelog = json.loads(CHANGELOG.read_text(encoding="utf-8")) if CHANGELOG.is_file() else {"entries": []}
    if args.assert_changelog:
        latest = {}
        for item in changelog.get("entries", []):
            latest[item.get("template_id")] = item
        for entry in registry.get("templates", []):
            template = json.loads((TEMPLATES / entry["file"]).read_text(encoding="utf-8"))
            record = latest.get(entry.get("template_id"))
            if record is None:
                errors.append(f"{entry.get('template_id')}: no changelog entry")
                continue
            if record.get("version") != template.get("template_version"):
                errors.append(f"{entry.get('template_id')}: version mismatch")
            if record.get("sections_sha256") != render.sections_sha256(template):
                errors.append(f"{entry.get('template_id')}: sections changed without version bump")
    for item in errors:
        print(item, file=sys.stderr)
    print(f"WB-TEMPLATES: templates={len(seen)} errors={len(errors)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())