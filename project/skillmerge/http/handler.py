from __future__ import annotations

import json
import uuid
from http.server import BaseHTTPRequestHandler

from ..util.errors import DomainError
from ..util.logging import get_logger, redact
from . import middleware
from .errors import error_payload, status_for
from .response import error_payload as wrap_error
from .response import ok_payload, send_file, send_json
from .router import build_request
from .sse import stream_events
from .static import serve_static


class RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "SkillMerge"
    sys_version = ""

    def version_string(self) -> str:
        return self.server_version

    def send_response(self, code, message=None) -> None:
        self.log_request(code)
        self.send_response_only(code, message)

    def log_message(self, fmt: str, *args) -> None:
        get_logger().info(redact("%s - %s" % (self.address_string(), fmt % args)))

    def log_error(self, fmt: str, *args) -> None:
        get_logger().warning(redact("%s - %s" % (self.address_string(), fmt % args)))

    def send_error(self, code: int, message: str = None, explain: str = None) -> None:
        status = int(code) if code else 400
        payload = wrap_error({"code": "BAD_REQUEST", "message": message or "请求失败", "fix": "检查请求后重试"})
        try:
            send_json(self, status, payload, {"Connection": "close"})
        except Exception:
            pass
        self.close_connection = True

    def do_OPTIONS(self) -> None:
        self._error(DomainError("METHOD_NOT_ALLOWED", "不支持 OPTIONS", "使用 GET 或 POST", 405))

    def do_HEAD(self) -> None:
        self._error(DomainError("METHOD_NOT_ALLOWED", "不支持 HEAD", "使用 GET", 405))

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        request_id = uuid.uuid4().hex[:12]
        try:
            middleware.check_host(self, self.server.port)
            if method == "GET":
                if serve_static(self, self.path.split("?", 1)[0], self.server.web_dir, self.server.token):
                    return
            request = build_request(method, self.path, self.headers, raw_handler=self)
            middleware.authenticate(self, self.server.token)
            if method == "POST":
                request.body = middleware.read_body(self)
                middleware.check_content_type(self)
                middleware.check_csrf(self)
                middleware.check_origin(self, self.server.port)
                request.json_data = middleware.parse_json(request.body)
            route, params = self.server.router.match(method, request.path)
            request.params = params
            request.sse = route.sse
            if route.sse:
                stream_events(self, self.server.events, self.server.job_store, params.get("id", ""))
                return
            if route.file:
                payload = route.handler(self.server.ctx, request)
                send_file(self, payload["path"], payload["filename"])
                return
            result = route.handler(self.server.ctx, request)
            status, data = result if isinstance(result, tuple) else (200, result)
            send_json(self, int(status), ok_payload(data))
        except DomainError as exc:
            self._error(exc, request_id)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True
        except Exception as exc:  # noqa: BLE001
            get_logger().error("request_id=%s %s", request_id, redact(str(exc)))
            self._error(DomainError("INTERNAL_ERROR", "服务内部错误", f"查看 stderr 日志中的 request_id={request_id} 后重试", 500))

    def _error(self, exc: DomainError, request_id: str = "") -> None:
        if exc.code == "INTERNAL_ERROR":
            exc.fix = exc.fix or f"查看 stderr 日志中的 request_id={request_id} 后重试"
        send_json(self, status_for(exc), wrap_error(error_payload(exc)))