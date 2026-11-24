from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.parse import quote

API_VERSION = "1.1"

SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    ),
}


def _encode(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def ok_payload(data: Any) -> Dict[str, Any]:
    return {"ok": True, "data": data, "meta": {"api_version": API_VERSION}}


def error_payload(error: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": False, "error": error}


def send_json(handler, status: int, payload: Dict[str, Any], extra_headers: Optional[Dict[str, str]] = None) -> None:
    body = _encode(payload)
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    for key, value in SECURITY_HEADERS.items():
        handler.send_header(key, value)
    for key, value in (extra_headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        handler.close_connection = True


def send_file(handler, path: str, filename: str) -> None:
    with open(path, "rb") as handle:
        body = handle.read()
    content_type = "application/zip" if filename.lower().endswith(".zip") else "application/octet-stream"
    disposition = "attachment; filename*=UTF-8''" + quote(filename, safe="")
    send_bytes(handler, 200, body, content_type, {"Content-Disposition": disposition})


def send_bytes(handler, status: int, body: bytes, content_type: str, extra_headers: Optional[Dict[str, str]] = None) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    for key, value in SECURITY_HEADERS.items():
        handler.send_header(key, value)
    for key, value in (extra_headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except (BrokenPipeError, ConnectionResetError):
        handler.close_connection = True