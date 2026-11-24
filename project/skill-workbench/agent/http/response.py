"""Uniform success envelope and JSON writer."""
from __future__ import annotations

import json
from datetime import datetime, timezone

API_VERSION = "wb-1"


def meta(request_id: str = "") -> dict:
    return {
        "api_version": API_VERSION,
        "request_id": request_id,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


def envelope(data, request_id: str = "") -> dict:
    return {"ok": True, "data": data, "meta": meta(request_id)}


def write_json(handler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)