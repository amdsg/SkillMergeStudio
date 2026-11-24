"""Versioned render templates: load, validate, deterministic render."""
from __future__ import annotations

import json
import re
from pathlib import Path

from agent.core.hashing import sha256_text
from agent.http.errors import DomainError

TEMPLATES = Path(__file__).resolve().parents[1] / "adapters" / "templates"
ADAPTERS = Path(__file__).resolve().parents[1] / "adapters"
SCHEMA = json.loads((ADAPTERS / "intermediate_schema.json").read_text(encoding="utf-8"))
POLICY = json.loads((ADAPTERS / "feature_policy.json").read_text(encoding="utf-8"))
LIMIT_PATTERN = re.compile("|".join(SCHEMA.get("forbidden_value_patterns") or []), re.I)
CLAIM_PATTERN = re.compile("|".join(POLICY.get("claim_patterns") or []), re.I)
REQUIRED = ("template_id", "target_id", "template_version", "kind", "sections", "evidence_level")


def load_registry() -> dict:
    return json.loads((TEMPLATES / "_registry.json").read_text(encoding="utf-8"))


def load_template(template_id: str) -> dict:
    entry = next((item for item in load_registry().get("templates", []) if item.get("template_id") == template_id), None)
    if entry is None:
        raise DomainError("E_TEMPLATE_EVIDENCE_MISMATCH", "wb.error.template_evidence_mismatch", status=500,
                          params={"template_id": template_id}, fix_key="wb.fix.register_target")
    return json.loads((TEMPLATES / entry["file"]).read_text(encoding="utf-8"))


def sections_sha256(template: dict) -> str:
    return sha256_text(json.dumps(template.get("sections") or [], ensure_ascii=False, sort_keys=True))


def validate_template(template: dict) -> list[str]:
    errors = []
    for field in REQUIRED:
        if field not in template:
            errors.append(f"missing {field}")
    if not isinstance(template.get("template_version"), int):
        errors.append("template_version must be integer")
    sections = template.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections must be a non-empty ordered array")
    else:
        for section in sections:
            for field in ("heading", "required", "source_field"):
                if field not in section:
                    errors.append(f"section missing {field}")
    evidence = str(template.get("evidence_level", ""))
    target = str(template.get("target_id", ""))
    if evidence == "unknown" and target not in ("*", ""):
        errors.append("E_TEMPLATE_EVIDENCE_MISMATCH: unknown target must use generic template")
    text = json.dumps(template, ensure_ascii=False)
    if LIMIT_PATTERN.search(text):
        errors.append("forbidden limit value in template")
    if CLAIM_PATTERN.search(text):
        errors.append("forbidden official/compatible claim in template")
    return errors


def _value(doc: dict, path: str):
    holder = doc
    for part in path.split("."):
        if isinstance(holder, dict):
            holder = holder.get(part)
        else:
            return None
    return holder


def _render_list(value) -> str:
    lines = []
    for index, item in enumerate(value, 1):
        if isinstance(item, dict):
            text = str(item.get("text") or item.get("trigger") or "unknown")
            lines.append(f"{index}. {text}")
        else:
            lines.append(f"{index}. {item}")
    return "\n".join(lines)


def render(doc: dict, template: dict) -> str:
    errors = validate_template(template)
    if errors:
        raise DomainError("E_TEMPLATE_EVIDENCE_MISMATCH", "wb.error.template_evidence_mismatch", status=500,
                          params={"errors": errors}, fix_key="wb.fix.register_target")
    name = str((doc.get("identity") or {}).get("name") or "unknown")
    blocks = [f"# {name}", ""]
    for section in template["sections"]:
        value = _value(doc, section["source_field"])
        if not section.get("required") and not value:
            continue
        blocks.append(f"## {section['heading']}")
        if isinstance(value, list):
            blocks.append(_render_list(value) if value else "unknown")
        elif isinstance(value, dict):
            blocks.append(json.dumps(value, ensure_ascii=False, indent=1))
        elif value is None or value == "":
            blocks.append("unknown")
        else:
            blocks.append(str(value))
        blocks.append("")
    blocks.append("## Feature differences")
    blocks.append("No feature differences.")
    blocks.append("")
    return "\n".join(blocks)