"""Standard-library HTTP server for the local agent."""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from agent.http.errors import DomainError
from agent.http.router import RouteNotFound, Router
from agent.http.response import envelope, write_json


class _Handler(BaseHTTPRequestHandler):
    router: Router
    server_ref: "WorkbenchServer"

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        return

    def _handle(self) -> None:
        parsed = urlparse(self.path)
        request_id = self.headers.get("X-WB-Request-Id", "")
        try:
            handler, params = self.router.dispatch(self.command, parsed.path)
            body = b""
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length:
                body = self.rfile.read(length)
            result = handler(params, body, request_id)
            write_json(self, 200, envelope(result, request_id))
        except RouteNotFound:
            write_json(self, 404, {"ok": False, "error": {"code": "E_NOT_FOUND", "message_key": "wb.error.not_found", "params": {}, "fix_key": "wb.fix.check_path"}})
        except DomainError as error:
            write_json(self, error.status, error.payload())
        except (ValueError, json.JSONDecodeError):
            write_json(self, 400, {"ok": False, "error": {"code": "E_BAD_REQUEST", "message_key": "wb.error.bad_request", "params": {}, "fix_key": "wb.fix.check_input"}})
        except Exception:
            write_json(self, 500, {"ok": False, "error": {"code": "E_INTERNAL", "message_key": "wb.error.internal", "params": {}, "fix_key": "wb.fix.view_diagnostics"}})

    def do_GET(self):  # noqa: N802 - stdlib signature
        self._handle()

    def do_POST(self):  # noqa: N802 - stdlib signature
        self._handle()

    def do_DELETE(self):  # noqa: N802 - stdlib signature
        self._handle()


class WorkbenchServer:
    def __init__(self, router: Router, host: str = "127.0.0.1", port: int = 8788,
                 runtime_path: Path | None = None) -> None:
        self.router = router
        self.host = host
        self.requested_port = port
        self.runtime_path = runtime_path
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._httpd is None:
            return self.requested_port
        return int(self._httpd.server_address[1])

    def start(self) -> dict:
        handler_class = type("Handler", (_Handler,), {"router": self.router, "server_ref": self})
        try:
            self._httpd = ThreadingHTTPServer((self.host, self.requested_port), handler_class)
        except OSError as error:
            raise SystemExit(f"E_PORT_UNAVAILABLE: {self.host}:{self.requested_port} ({error})") from error
        self._httpd.daemon_threads = True
        info = {"host": self.host, "port": self.port, "pid": os.getpid(), "started_at": _now()}
        if self.runtime_path is not None:
            self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.runtime_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.runtime_path)
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="wb-agent", daemon=True)
        self._thread.start()
        return info

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
        if self.runtime_path is not None and self.runtime_path.exists():
            try:
                self.runtime_path.unlink()
            except OSError:
                pass


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()