"""Execution slots and idempotency keys shared inside one agent process."""
from __future__ import annotations

import threading
from datetime import datetime, timezone


class SlotBusy(Exception):
    pass


class JobSlots:
    def __init__(self) -> None:
        self._locks = {"merge": threading.Lock(), "convert": threading.Lock(), "write": threading.Lock()}

    def acquire(self, name: str) -> bool:
        lock = self._locks.get(name)
        if lock is None:
            return False
        return lock.acquire(blocking=False)

    def release(self, name: str) -> None:
        lock = self._locks.get(name)
        if lock is not None and lock.locked():
            lock.release()


class IdempotencyStore:
    def __init__(self) -> None:
        self._seen: dict[str, dict] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            return self._seen.get(key)

    def put(self, key: str, value: dict) -> None:
        with self._lock:
            self._seen[key] = {
                "value": value,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }