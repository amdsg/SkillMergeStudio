from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from ..storage.models import JobEvent
from ..storage.repos.jobs_repo import JobsRepo
from ..util.timeutil import utc_now_iso

BUFFER_SIZE = 256


class EventBroker:
    def __init__(self, repo: JobsRepo, throttle_seconds: float = 0.2, persist_every: int = 20) -> None:
        self.repo = repo
        self.throttle_seconds = throttle_seconds
        self.persist_every = persist_every
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._buffers: Dict[str, Deque[Dict[str, Any]]] = {}
        self._seq: Dict[str, int] = {}
        self._last_time: Dict[str, float] = {}
        self._last_phase: Dict[str, str] = {}
        self._counter: Dict[str, int] = {}

    def _buffer(self, job_id: str) -> Deque[Dict[str, Any]]:
        if job_id not in self._buffers:
            self._buffers[job_id] = deque(maxlen=BUFFER_SIZE)
            self._seq[job_id] = 0
            self._last_time[job_id] = 0.0
            self._last_phase[job_id] = ""
            self._counter[job_id] = 0
        return self._buffers[job_id]

    def publish(self, job_id: str, phase: str, current: int, total: Optional[int], message: str = "", force: bool = False) -> bool:
        now = time.monotonic()
        with self._cond:
            buffer = self._buffer(job_id)
            last = self._last_time.get(job_id, 0.0)
            phase_changed = phase != self._last_phase.get(job_id, "")
            if not force and not phase_changed and now - last < self.throttle_seconds:
                return False
            seq = int(self._seq.get(job_id, 0)) + 1
            self._seq[job_id] = seq
            self._last_time[job_id] = now
            self._last_phase[job_id] = phase
            event = {
                "seq": seq,
                "job_id": job_id,
                "phase": phase,
                "current": int(current),
                "total": total,
                "message": message,
                "created_at": utc_now_iso(),
            }
            buffer.append(event)
            self._counter[job_id] = int(self._counter.get(job_id, 0)) + 1
            if phase_changed or self._counter[job_id] % self.persist_every == 0:
                try:
                    self.repo.add_event(
                        JobEvent(
                            job_id=job_id,
                            seq=seq,
                            phase=phase,
                            current=int(current),
                            total=total,
                            message=message,
                            created_at=event["created_at"],
                        )
                    )
                    self._counter[job_id] = 0
                except Exception:
                    pass
            self._cond.notify_all()
            return True

    def events_since(self, job_id: str, last_seq: int = 0) -> List[Dict[str, Any]]:
        with self._lock:
            buffer = self._buffer(job_id)
            in_memory = [dict(event) for event in buffer if int(event["seq"]) > int(last_seq)]
        if in_memory:
            return in_memory
        return self.repo.events_since(job_id, int(last_seq), BUFFER_SIZE)

    def wait_events(self, job_id: str, last_seq: int, timeout: float = 1.0) -> List[Dict[str, Any]]:
        with self._cond:
            buffer = self._buffer(job_id)
            if not any(int(event["seq"]) > int(last_seq) for event in buffer):
                self._cond.wait(timeout)
            return [dict(event) for event in buffer if int(event["seq"]) > int(last_seq)]

    def next_seq(self, job_id: str) -> int:
        with self._lock:
            self._buffer(job_id)
            return int(self._seq.get(job_id, 0))

    def close(self, job_id: str) -> None:
        with self._cond:
            self._cond.notify_all()