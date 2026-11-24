"""Conversion endpoint: tiered headers, generic fallback, no truncation."""
from __future__ import annotations

import json
import re

from pathlib import Path

from agent.adapters.loader import registry
from agent.api.convert import BINARY_SUFFIXES, MAX_TEXT_BYTES, convert as classify
from agent.core.hashing import sha256_file
from agent.core.index_store import unique_dir
from agent.core.intermediate import render_header
from agent.core.paths import data_dir
from agent.core.records import append
from agent.http.errors import DomainError

CONVERSIONS = data_dir() / "exports"
HEADING = re.compile(r"^(#{1,6})\s+(.+)$", re.M)


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _read_source(path: Path) -> str:
    entry = path / "SKILL.md" if path.is_dir() else path
    if not entry.is_file():
        candidate = next((item for item in sorted(path.rglob("*.md"))), None) if path.is_dir() else None
        if candidate is None:
            raise DomainError("E_BAD_REQUEST", "wb.error.bad_request",
                              params={"path": str(path)}, fix_key="wb.fix.check_input")
        entry = candidate
    return entry.read_text(encoding="utf-8", errors="replace")



def convert_endpoint(params, body, request_id):
    payload = _body(body)
    target_id = str(payload.get("target_id", ""))
    source_path = Path(str(payload.get("source_path", "")))
    if not source_path.exists():
        raise DomainError("E_SOURCE_NOT_DOWNLOADED", "wb.error.source_not_downloaded",
                          params={"path": str(source_path)}, fix_key="wb.fix.redownload_source")
    if source_path.suffix.lower() in BINARY_SUFFIXES:
        raise DomainError("E_UNSUPPORTED_BINARY", "wb.error.unsupported_binary",
                          params={"path": source_path.name}, fix_key="wb.fix.check_input")
    target = registry.get(target_id)
    fallback = bool(payload.get("fallback_generic"))
    requested_raw = ""
    if target is None:
        if not fallback:
            raise DomainError("E_TARGET_NOT_REGISTERED", "wb.error.target_not_registered",
                              params={"target": target_id}, fix_key="wb.fix.register_target")
        requested_raw = target_id
        kind = str(payload.get("kind", "prompt"))
        generic_id = "agent_skills_generic" if kind == "skill" else "prompt_only_generic"
        target = registry.get(generic_id)
        if target is None:
            raise DomainError("E_TARGET_REGISTRY_INVALID", "wb.error.target_registry_invalid",
                              params={"target": generic_id}, fix_key="wb.fix.register_target")
    kind = str(payload.get("source_kind", target.get("kind", "prompt")))
    text = _read_source(source_path)
    size = len(text.encode("utf-8"))
    classification = classify(target, kind, size)
    target_dir = unique_dir(CONVERSIONS, f"{target_id or 'generic'}-{hashlib_id(text)}")
    target_dir.mkdir(parents=True, exist_ok=True)
    head = render_header(target, classification["tier"], requested_raw)
    body_text = text if "\n" in text else text + "\n"
    output = head + "\n" + body_text
    files = []
    if kind == "skill":
        entry = target_dir / "SKILL.md"
        entry.write_text(output, encoding="utf-8")
        files.append("SKILL.md")
    else:
        entry = target_dir / "prompt.md"
        entry.write_text(output, encoding="utf-8")
        files.append("prompt.md")
    before = set(HEADING.findall(text))
    after = set(HEADING.findall(output))
    lost = sorted(f"{'#' * len(level)} {title}" for level, title in before - after)
    record = append("conversions", {
        "state": "completed",
        "target_id": str(target.get("id", "")),
        "requested_target_raw": requested_raw,
        "tier": classification["tier"],
        "source_sha256": sha256_file(source_path) if source_path.is_file() else "",
        "files": files,
        "lost_chapters": lost,
    })
    return {
        "record_id": str(record.get("created_at")),
        "artifact_dir": f"conversions/{target_dir.name}",
        "files": files,
        "tier": classification["tier"],
        "head": head,
        "source_kind": kind,
        "requested_target_raw": requested_raw,
        "fallback_required": classification["fallback_required"],
        "lost_chapters": lost,
        "text_bytes": size,
    }


def hashlib_id(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]