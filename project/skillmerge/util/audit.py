from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from .logging import redact
from .timeutil import utc_now_iso

ACTIONS = ("merge", "export", "install", "undo", "rebuild", "config")
_LOCK = threading.Lock()


def audit_log_path(data_dir: str) -> str:
    return os.path.join(data_dir, "audit.log")


def write_audit(
    data_dir: str,
    action: str,
    target: str,
    result: str,
    detail: Optional[Dict[str, Any]] = None,
) -> bool:
    if action not in ACTIONS:
        raise ValueError(f"unknown audit action: {action}")
    record: Dict[str, Any] = {
        "at": utc_now_iso(),
        "action": action,
        "target": str(target),
        "result": str(result),
        "operator": "local",
    }
    if detail is not None:
        record["detail"] = detail
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    path = audit_log_path(data_dir)
    with _LOCK:
        try:
            os.makedirs(data_dir, exist_ok=True)
            with open(path, "a", encoding="utf-8", newline="\n") as handle:
                handle.write(redact(line) + "\n")
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
            return True
        except OSError:
            return False


def read_audit(data_dir: str, limit: int = 100) -> List[Dict[str, Any]]:
    path = audit_log_path(data_dir)
    if not os.path.isfile(path):
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except ValueError:
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows[-max(1, int(limit)):][::-1]