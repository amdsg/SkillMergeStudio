"""Conversion entry points: tiered output with a generic Fallback path."""
from __future__ import annotations

from agent.http.errors import DomainError

GENERIC_FALLBACK_BY_KIND = {"skill": "generic_skill", "prompt": "generic_prompt"}
BINARY_SUFFIXES = (".pptx", ".docx", ".pdf", ".xlsx")
MAX_TEXT_BYTES = 1024 * 1024


def _fallback(kind: str) -> str:
    return GENERIC_FALLBACK_BY_KIND.get(kind, "generic_prompt")


def convert(target: dict, source_kind: str, size_bytes: int = 0) -> dict:
    if not target or target.get("enabled") is False:
        raise DomainError("E_TARGET_NOT_REGISTERED", "wb.error.target_not_registered",
                          params={"target": str((target or {}).get("id", ""))}, fix_key="wb.fix.register_target")
    if size_bytes > MAX_TEXT_BYTES:
        raise DomainError("E_LIMIT_EXCEEDED", "wb.error.text_too_large",
                          params={"limit": MAX_TEXT_BYTES}, fix_key="wb.fix.split_source")
    level = str(target.get("evidence_level", "unknown"))
    subtype = str(target.get("evidence_subtype") or "")
    if level == "verified" and subtype == "official":
        tier = "official"
    elif level == "verified":
        tier = "local_contract"
    elif level == "candidate":
        tier = "candidate"
    else:
        tier = "generic"
    return {
        "target_id": str(target.get("id", "")),
        "tier": tier,
        "kind": source_kind,
        "fallback_target_kind": _fallback(source_kind),
        "fallback_required": level != "verified",
        "format_profile": str(target.get("format_profile", "unknown")),
    }