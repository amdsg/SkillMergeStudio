from __future__ import annotations

import json
import time
from typing import Any

from ..util.errors import DomainError
from .response import SECURITY_HEADERS


def _write(handler, chunk: str) -> bool:
    try:
        handler.wfile.write(chunk.encode("utf-8"))
        handler.wfile.flush()
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False


def stream_events(handler, broker, store, job_id: str) -> None:
    job = store.get(job_id)
    if job is None:
        raise DomainError("NOT_FOUND", f"任务不存在：{job_id}", "刷新任务列表后重试", 404)
    last_seq = 0
    header_seq = handler.headers.get("Last-Event-ID", "") if handler.headers else ""
    if header_seq.isdigit():
        last_seq = int(header_seq)
    handler.send_response(200)
    handler.send_header("Content-Type", "text/event-stream; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Connection", "keep-alive")
    handler.send_header("X-Accel-Buffering", "no")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.close_connection = True
    last_heartbeat = time.monotonic()
    terminal = {"succeeded", "failed", "cancelled"}
    idle_after_terminal = 0
    while True:
        events = broker.events_since(job_id, last_seq)
        if not events:
            events = broker.wait_events(job_id, last_seq, timeout=1.0)
        for event in events:
            last_seq = int(event["seq"])
            frame = f"id: {last_seq}\ndata: {json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
            if not _write(handler, frame):
                return
            idle_after_terminal = 0
        current = store.get(job_id)
        if current is not None and current.status in terminal:
            if not events:
                idle_after_terminal += 1
            if idle_after_terminal >= 2:
                _write(handler, f"event: done\ndata: {json.dumps({'status': current.status}, ensure_ascii=False)}\n\n")
                return
        now = time.monotonic()
        if now - last_heartbeat >= 15:
            if not _write(handler, ": ping\n\n"):
                return
            last_heartbeat = now