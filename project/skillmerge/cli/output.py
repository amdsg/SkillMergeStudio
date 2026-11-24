from __future__ import annotations

import json
import sys
from typing import Any


def emit(data: Any) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def emit_error(code: str, message: str, fix: str = "") -> None:
    emit({"ok": False, "error": {"code": code, "message": message, "fix": fix or "检查命令参数后重试"}})


def log(message: str) -> None:
    print(message, file=sys.stderr)