"""Vendor-neutral intermediate document: load, validate, dump, view migration."""
from __future__ import annotations

import json
import re
from pathlib import Path

from agent.http.errors import DomainError

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "adapters" / "intermediate_schema.json"
CURRENT_SCHEMA_VERSION = 1
REQUIRED_KEYS = (
    "schema_version", "identity", "intent", "capabilities", "instructions",
    "examples", "resources", "provenance",
)
IDENTITY_FIELDS = ("name", "id", "version", "tags")
CAPABILITY_FIELDS = ("trigger", "inputs", "outputs", "constraints")
PROVENANCE_FIELDS = ("source", "native_targets", "import_id", "mapping_report_ref")
EMPTY_ALLOWED = ("identity.tags", "examples", "resources", "provenance.native_targets")


def load_schema() -> dict:
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DomainError("E_INTERMEDIATE_INVALID", "wb.error.intermediate_invalid",
                          params={"field": "schema", "expected": "readable", "actual": str(error)},
                          fix_key="wb.fix.check_input") from error


def _issues(field: str, code: str, expected, actual) -> dict:
    return {"field": field, "code": code, "expected": expected, "actual": actual}


def _iter_pairs(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            yield path, key, item
            yield from _iter_pairs(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]"
            if isinstance(item, (dict, list)):
                yield from _iter_pairs(item, path)
            else:
                yield path, "", item


def validate(doc) -> list[dict]:
    schema = load_schema()
    errors: list[dict] = []
    if not isinstance(doc, dict):
        return [_issues("$", "not_an_object", "object", type(doc).__name__)]
    keys = set(doc)
    missing = set(REQUIRED_KEYS) - keys
    extra = keys - set(REQUIRED_KEYS)
    for key in sorted(missing):
        errors.append(_issues(key, "missing_key", "required", "absent"))
    for key in sorted(extra):
        errors.append(_issues(key, "unknown_key", "not_allowed", key))
    version = doc.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        errors.append(_issues("schema_version", "not_integer", "integer", type(version).__name__))
    elif version < 1:
        errors.append(_issues("schema_version", "invalid", ">=1", version))
    identity = doc.get("identity")
    if not isinstance(identity, dict):
        errors.append(_issues("identity", "not_an_object", "object", type(identity).__name__))
    else:
        for field in IDENTITY_FIELDS:
            if field not in identity:
                errors.append(_issues(f"identity.{field}", "missing_key", "required", "absent"))
        for key in set(identity) - set(IDENTITY_FIELDS):
            errors.append(_issues(f"identity.{key}", "unknown_key", "not_allowed", key))
    intent = doc.get("intent")
    if not isinstance(intent, dict) or not str(intent.get("summary", "")).strip():
        errors.append(_issues("intent.summary", "missing_value", "non-empty", intent))
    capabilities = doc.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        errors.append(_issues("capabilities", "empty_not_allowed", ">=1 item", capabilities))
    else:
        for index, item in enumerate(capabilities):
            if not isinstance(item, dict):
                errors.append(_issues(f"capabilities[{index}]", "not_an_object", "object", type(item).__name__))
                continue
            for field in CAPABILITY_FIELDS:
                if field not in item:
                    errors.append(_issues(f"capabilities[{index}].{field}", "missing_key", "required", "absent"))
    instructions = doc.get("instructions")
    if not isinstance(instructions, list) or not instructions:
        errors.append(_issues("instructions", "empty_not_allowed", "ordered array >=1", instructions))
    else:
        for index, item in enumerate(instructions):
            if not isinstance(item, dict) or "text" not in item:
                errors.append(_issues(f"instructions[{index}]", "invalid_item", "object with text", item))
    for field in ("examples", "resources"):
        value = doc.get(field)
        if not isinstance(value, list):
            errors.append(_issues(field, "not_an_array", "array", type(value).__name__))
    provenance = doc.get("provenance")
    if not isinstance(provenance, dict):
        errors.append(_issues("provenance", "not_an_object", "object", type(provenance).__name__))
    else:
        for field in PROVENANCE_FIELDS:
            if field not in provenance:
                errors.append(_issues(f"provenance.{field}", "missing_key", "required", "absent"))
    forbidden = [re.compile(pattern) for pattern in schema.get("forbidden_field_names", [])]
    patterns = [re.compile(pattern, re.I) for pattern in schema.get("forbidden_value_patterns", [])]
    for path, key, value in _iter_pairs(doc):
        for pattern in forbidden:
            if pattern.match(str(key)):
                errors.append(_issues(path, "forbidden_field_name", "vendor_neutral", key))
        if isinstance(value, str):
            for pattern in patterns:
                match = pattern.search(value)
                if match:
                    errors.append(_issues(path, "forbidden_value_pattern", "vendor_neutral", match.group(0)))
    for path in EMPTY_ALLOWED:
        holder = doc
        for part in path.split("."):
            holder = holder.get(part) if isinstance(holder, dict) else None
        if holder is None:
            errors.append(_issues(path, "missing_value", "array (may be empty)", "absent"))
    if isinstance(provenance, dict) and isinstance(provenance.get("native_targets"), str):
        errors.append(_issues("provenance.native_targets", "not_an_array", "array or unknown", "string"))
    return errors


def require_valid(doc) -> None:
    errors = validate(doc)
    if errors:
        first = errors[0]
        raise DomainError("E_INTERMEDIATE_INVALID", "wb.error.intermediate_invalid",
                          params=first, fix_key="wb.fix.check_input")


def require_intermediate(doc) -> None:
    if doc is None:
        raise DomainError("E_INTERMEDIATE_REQUIRED", "wb.error.intermediate_required",
                          params={"field": "$", "expected": "intermediate document", "actual": "absent"},
                          fix_key="wb.fix.import_first")
    require_valid(doc)


def load(text: str) -> dict:
    try:
        doc = json.loads(text)
    except ValueError as error:
        raise DomainError("E_INTERMEDIATE_INVALID", "wb.error.intermediate_invalid",
                          params={"field": "json", "expected": "object", "actual": str(error)},
                          fix_key="wb.fix.check_input") from error
    require_valid(doc)
    return doc


def dump(doc: dict) -> str:
    require_valid(doc)
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


def migrate_view(doc: dict) -> dict:
    if not isinstance(doc, dict):
        raise DomainError("E_INTERMEDIATE_INVALID", "wb.error.intermediate_invalid",
                          params={"field": "$", "expected": "object", "actual": type(doc).__name__},
                          fix_key="wb.fix.check_input")
    version = doc.get("schema_version")
    if not isinstance(version, int) or version > CURRENT_SCHEMA_VERSION:
        raise DomainError("E_INTERMEDIATE_SCHEMA_TOO_OLD", "wb.error.intermediate_schema_too_old",
                          params={"field": "schema_version", "expected": f"<={CURRENT_SCHEMA_VERSION}", "actual": version},
                          fix_key="wb.fix.check_input")
    view = json.loads(json.dumps(doc))
    if version < CURRENT_SCHEMA_VERSION:
        view["schema_version"] = CURRENT_SCHEMA_VERSION
        identity = view.setdefault("identity", {})
        identity.setdefault("tags", [])
        view.setdefault("examples", [])
        view.setdefault("resources", [])
        provenance = view.setdefault("provenance", {})
        provenance.setdefault("native_targets", ["unknown"])
    return view


def render_header(target: dict, tier: str, requested_raw: str = "") -> str:
    """Header text shared by exporters. Kept here so no module bypasses the layer."""
    if tier == "official":
        return f"Format: {target.get('label')} (official structure)\nSource: {target.get('source')}\nVerified: {target.get('verified_at')}\n"
    if tier == "local_contract":
        return "Format: local contract (no vendor endorsement)\n"
    if tier == "candidate":
        return f"Format: unverified (candidate)\nNote: structure not verified for {target.get('label')}\n"
    if requested_raw:
        return f"Format: generic text (target not verified)\nRequested target: {requested_raw} (not registered)\nNote: generated as generic text\n"
    return f"Format: generic text (target not verified)\nNote: structure not verified for {target.get('label')}\n"