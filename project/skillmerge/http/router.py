from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlsplit

from ..util.errors import DomainError


@dataclass
class Request:
    method: str
    path: str
    query: Dict[str, List[str]]
    headers: Any
    body: bytes = b""
    json_data: Any = None
    params: Dict[str, str] = field(default_factory=dict)
    raw_handler: Any = None
    sse: bool = False

    def q(self, name: str, default: str = "") -> str:
        values = self.query.get(name)
        return values[0] if values else default

    def q_int(self, name: str, default: int) -> int:
        raw = self.q(name, "")
        if raw == "":
            return default
        try:
            return int(raw)
        except ValueError:
            raise DomainError("INVALID_ARGUMENT", f"参数 {name} 必须是整数", f"将 {name} 改为整数")


@dataclass
class Route:
    method: str
    pattern: str
    handler: Callable[[Any, Request], Any]
    regex: Any
    sse: bool = False
    file: bool = False


class Router:
    def __init__(self) -> None:
        self._routes: List[Route] = []

    def add(self, method: str, pattern: str, handler: Callable[[Any, Request], Any], sse: bool = False, file: bool = False) -> None:
        regex = self._compile(pattern)
        self._routes.append(Route(method.upper(), pattern, handler, regex, sse, file))

    @staticmethod
    def _compile(pattern: str):
        pieces = re.split(r"(\{[a-zA-Z_][a-zA-Z0-9_]*\})", pattern)
        out = []
        for piece in pieces:
            if piece.startswith("{") and piece.endswith("}"):
                out.append(f"(?P<{piece[1:-1]}>[^/]+)")
            else:
                out.append(re.escape(piece))
        return re.compile("^" + "".join(out) + "$")

    def match(self, method: str, path: str) -> Tuple[Route, Dict[str, str]]:
        path_matched = False
        for route in self._routes:
            match = route.regex.match(path)
            if not match:
                continue
            path_matched = True
            if route.method == method.upper():
                return route, match.groupdict()
        if path_matched:
            raise DomainError("METHOD_NOT_ALLOWED", f"{method} 不被该路径支持", "使用正确的 HTTP 方法", 405)
        raise DomainError("NOT_FOUND", f"路径不存在：{path}", "检查接口路径或刷新页面", 404)

    def has(self, method: str, path: str) -> bool:
        try:
            self.match(method, path)
            return True
        except DomainError:
            return False


def build_request(method: str, raw_path: str, headers, body: bytes = b"", json_data: Any = None, raw_handler: Any = None) -> Request:
    parsed = urlsplit(raw_path)
    return Request(
        method=method.upper(),
        path=parsed.path or "/",
        query=parse_qs(parsed.query, keep_blank_values=True),
        headers=headers,
        body=body,
        json_data=json_data,
        raw_handler=raw_handler,
    )