"""Path anchors and user-path redaction."""
from __future__ import annotations

import os
from pathlib import Path

WB_ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    return Path(os.environ.get("WB_DATA_DIR") or (WB_ROOT / "data"))


def store_dir() -> Path:
    return Path(os.environ.get("WB_STORE_DIR") or (WB_ROOT / "agent" / "store"))


STORE_DIR = store_dir()
RECORDS_DIR = STORE_DIR / "records"
SNAPSHOTS_DIR = STORE_DIR / "snapshots"


def ensure_store() -> None:
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def redact_path(value: str) -> str:
    home = os.path.expanduser("~")
    if home and home in value:
        return value.replace(home, "<home>")
    return value