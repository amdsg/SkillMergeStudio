"""POST /import: dry-run report, then atomic write into the pending import partition."""
from __future__ import annotations

import json
from pathlib import Path

from agent.core import intermediate
from agent.core.hashing import sha256_text
from agent.core.import_detect import detect
from agent.core.import_map import build
from agent.core.index_store import build_entry
from agent.core.limits import IdempotencyStore, JobSlots
from agent.core.paths import data_dir
from agent.core.records import append
from agent.http.errors import DomainError

IMPORTS = data_dir() / "imports"
SLOTS = JobSlots()
IDEMPOTENCY = IdempotencyStore()


def _body(raw: bytes) -> dict:
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def _source_text(payload: dict) -> str:
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text
    source_path = Path(str(payload.get("source_path", "")))
    if source_path.is_file():
        return source_path.read_text(encoding="utf-8", errors="replace")
    raise DomainError("E_BAD_REQUEST", "wb.error.bad_request", status=400,
                      params={"fields": ["text", "source_path"]}, fix_key="wb.fix.check_input")


def import_endpoint(params, body, request_id):
    payload = _body(body)
    text = _source_text(payload)
    detected = detect(text, str(payload.get("profile_id", "")))
    doc, report = build(
        text,
        detected["profile_id"],
        detected["format_recognized"],
        source=str(payload.get("source", "unknown")),
        overrides=payload.get("overrides") if isinstance(payload.get("overrides"), dict) else None,
    )
    errors = intermediate.validate(doc)
    if errors:
        raise DomainError("E_INTERMEDIATE_INVALID", "wb.error.intermediate_invalid", status=400,
                          params=errors[0], fix_key="wb.fix.check_input")
    dry_run = bool(payload.get("dry_run", True))
    if dry_run:
        return {"dry_run": True, "report": report, "intermediate": doc, "writes": 0}

    key = str(payload.get("idempotency_key", ""))
    if not (8 <= len(key) <= 128):
        raise DomainError("E_BAD_REQUEST", "wb.error.bad_request", status=400,
                          params={"field": "idempotency_key"}, fix_key="wb.fix.check_input")
    cached = IDEMPOTENCY.get(key)
    if cached is not None:
        return {**cached["value"], "reused": True}
    if not SLOTS.acquire("convert"):
        raise DomainError("E_JOB_BUSY", "wb.error.job_busy", status=429,
                          params={"busy_slot": "convert", "retry_after_ms": 1500}, fix_key="wb.fix.retry_later")
    try:
        import_id = report["import_id"]
        target = IMPORTS / import_id
        target.mkdir(parents=True, exist_ok=True)
        intermediate_path = target / "intermediate.json"
        intermediate_path.write_text(intermediate.dump(doc), encoding="utf-8", newline="\n")
        entry = build_entry(import_id, doc["identity"]["name"], str(payload.get("source", "unknown")),
                            str(payload.get("source_commit", "unknown")),
                            {"fields": {"native_targets": ["unknown"], "capability_tags": [], "version": doc["identity"]["version"]},
                             "parse_status": "partial"}, f"imports/{import_id}")
        (target / "manifest.json").write_text(json.dumps({"index_entry": entry, "report": report}, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        append("imports", {"state": "completed", "import_id": import_id, "profile_id": detected["profile_id"],
                           "summary": report["summary"], "source_sha256": sha256_text(text)})
        result = {
            "dry_run": False,
            "import_id": import_id,
            "report": report,
            "files": ["intermediate.json", "manifest.json"],
            "partition": "pending",
            "reused": False,
        }
        IDEMPOTENCY.put(key, result)
        return result
    finally:
        SLOTS.release("convert")