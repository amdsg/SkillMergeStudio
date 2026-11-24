"""Append-only JSONL records with atomic snapshots."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from agent.core.paths import RECORDS_DIR, SNAPSHOTS_DIR


def append(name: str, payload: dict) -> dict:
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    record = dict(payload)
    record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    path = RECORDS_DIR / f"{name}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_all(name: str) -> list[dict]:
    path = RECORDS_DIR / f"{name}.jsonl"
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def snapshot(name: str, payload: dict) -> Path:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "schema_version": 1,
        "name": name,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    target = SNAPSHOTS_DIR / f"{name}.json"
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, target)
    return target


def scan_interrupted() -> list[dict]:
    interrupted = []
    for record in read_all("installs") + read_all("upgrades"):
        if record.get("state") in ("running", "planned", "awaiting_confirm"):
            record["state"] = "interrupted"
            interrupted.append(record)
    return interrupted