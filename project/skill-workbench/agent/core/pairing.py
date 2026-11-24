"""One-time pairing codes: 24 chars, TTL <=120s, single use, pair.txt 0600."""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

from agent.http.errors import DomainError

CODE_TTL_SECONDS = 120
CODE_LENGTH = 24
PAIR_FILE = "pair.txt"


class PairingStore:
    def __init__(self, store_dir: Path, ttl: int = CODE_TTL_SECONDS, clock=time.time) -> None:
        self._dir = store_dir
        self._ttl = min(int(ttl), CODE_TTL_SECONDS)
        self._clock = clock
        self._records: dict[str, dict] = {}

    def create(self) -> dict:
        code = secrets.token_urlsafe(18)[:CODE_LENGTH]
        while code in self._records:
            code = secrets.token_urlsafe(18)[:CODE_LENGTH]
        self._records[code] = {"expires_at": self._clock() + self._ttl, "used": False}
        self._write_pair_file(code)
        return {"code": code, "expires_in": self._ttl}

    def consume(self, code: str) -> bool:
        record = self._records.get(str(code or ""))
        if record is None:
            raise DomainError("E_PAIR_CODE_INVALID", "wb.error.pair_code_invalid", status=401,
                              params={"field": "code"}, fix_key="wb.fix.pair_again")
        if record["used"]:
            raise DomainError("E_PAIR_CODE_USED", "wb.error.pair_code_used", status=401,
                              params={"field": "code"}, fix_key="wb.fix.pair_again")
        if self._clock() > record["expires_at"]:
            raise DomainError("E_PAIR_CODE_EXPIRED", "wb.error.pair_code_expired", status=401,
                              params={"ttl_seconds": self._ttl}, fix_key="wb.fix.pair_again")
        record["used"] = True
        return True

    def _write_pair_file(self, code: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / PAIR_FILE
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            os.write(descriptor, f"{code}\n".encode("utf-8"))
        finally:
            os.close(descriptor)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass