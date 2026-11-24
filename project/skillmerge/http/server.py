from __future__ import annotations

from http.server import ThreadingHTTPServer
from typing import Any, Tuple

from ..util.errors import DomainError
from .handler import RequestHandler


class SkillMergeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, handler_class, ctx, router, token, web_dir: str, events, job_store) -> None:
        super().__init__(address, handler_class)
        self.ctx = ctx
        self.router = router
        self.token = token
        self.web_dir = web_dir
        self.events = events
        self.job_store = job_store
        self.port = address[1]


def create_server(
    host: str,
    router,
    token,
    web_dir: str,
    events,
    job_store,
    ctx,
    preferred_port: int = 8765,
    end_port: int = 8865,
) -> Tuple[SkillMergeHTTPServer, int]:
    last_error = None
    if preferred_port == 0:
        server = SkillMergeHTTPServer(
            (host, 0), RequestHandler, ctx, router, token, web_dir, events, job_store
        )
        server.port = server.server_address[1]
        return server, server.port
    ports = range(preferred_port, max(preferred_port, end_port) + 1)
    for port in ports:
        try:
            server = SkillMergeHTTPServer(
                (host, port), RequestHandler, ctx, router, token, web_dir, events, job_store
            )
            return server, port
        except OSError as exc:
            last_error = exc
            continue
    raise DomainError(
        "PORT_UNAVAILABLE",
        f"端口 {ports.start}-{ports.stop - 1} 均被占用",
        "关闭占用端口的程序，或使用 --port 指定其他端口",
        500,
    ) from last_error