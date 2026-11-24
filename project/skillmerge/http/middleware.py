from __future__ import annotations

import json
from http.cookies import SimpleCookie
from typing import Any, Dict, Optional

from ..security import COOKIE_NAME, HEADER_NAME, SessionToken, host_allowed, origin_allowed
from ..util.errors import DomainError

MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_HEADER_BYTES = 32 * 1024
MAX_HEADER_LINE = 8 * 1024


def check_host(handler, port: int) -> None:
    host = handler.headers.get("Host", "") if handler.headers else ""
    if not host_allowed(host, port):
        raise DomainError("HOST_FORBIDDEN", "Host 不在白名单", "使用 http://127.0.0.1:%d 访问，勿修改 Host" % port, 403)


def check_header_sizes(handler) -> None:
    total = 0
    for name, value in (handler.headers.items() if handler.headers else []):
        line_size = len(name) + len(value)
        if line_size > MAX_HEADER_LINE:
            raise DomainError("HEADERS_TOO_LARGE", "请求头单行过大", "减少 Cookie 或自定义头长度", 400)
        total += line_size
    if total > MAX_HEADER_BYTES:
        raise DomainError("HEADERS_TOO_LARGE", "请求头总大小超过 32KB", "清理 Cookie 后重试", 400)


def _read_chunked(handler) -> bytes:
    chunks = []
    total = 0
    while True:
        line = handler.rfile.readline(1024).strip()
        if not line:
            break
        try:
            size = int(line.split(b";", 1)[0], 16)
        except ValueError:
            raise DomainError("BAD_REQUEST", "chunked 请求体格式错误", "改用 Content-Length 提交 JSON")
        if size == 0:
            while True:
                trailer = handler.rfile.readline(1024)
                if trailer in (b"\r\n", b"\n", b""):
                    break
            break
        total += size
        if total > MAX_BODY_BYTES:
            handler.close_connection = True
            raise DomainError("PAYLOAD_TOO_LARGE", "请求体超过 5MB", "减少 sources 数量或改用 artifact_id", 413)
        chunk = handler.rfile.read(size)
        chunks.append(chunk)
        handler.rfile.read(2)
    return b"".join(chunks)


def read_body(handler) -> bytes:
    check_header_sizes(handler)
    transfer = (handler.headers.get("Transfer-Encoding", "") if handler.headers else "").lower()
    if "chunked" in transfer:
        return _read_chunked(handler)
    raw_length = handler.headers.get("Content-Length") if handler.headers else None
    if raw_length is None:
        raise DomainError("BAD_REQUEST", "缺少 Content-Length", "提交 JSON 并携带 Content-Length")
    try:
        length = int(raw_length)
    except ValueError:
        raise DomainError("BAD_REQUEST", "Content-Length 非法", "使用十进制字节数")
    if length < 0:
        raise DomainError("BAD_REQUEST", "Content-Length 非法", "使用非负整数")
    if length > MAX_BODY_BYTES:
        handler.close_connection = True
        raise DomainError("PAYLOAD_TOO_LARGE", "请求体超过 5MB", "减少 sources 数量或改用 artifact_id", 413)
    body = handler.rfile.read(length) if length else b""
    if len(body) != length:
        raise DomainError("BAD_REQUEST", "请求体长度不足", "确认网络传输完整后重试")
    return body


def check_content_type(handler) -> None:
    value = (handler.headers.get("Content-Type", "") if handler.headers else "").split(";", 1)[0].strip().lower()
    if value != "application/json":
        raise DomainError("BAD_REQUEST", "Content-Type 必须为 application/json", "设置 Content-Type: application/json")


def check_csrf(handler) -> None:
    value = handler.headers.get("X-Skillmerge", "") if handler.headers else ""
    if value != "1":
        raise DomainError("MISSING_CSRF_HEADER", "缺少 X-Skillmerge: 1 请求头", "在请求头加入 X-Skillmerge: 1")


def check_origin(handler, port: int) -> None:
    origin = handler.headers.get("Origin", "") if handler.headers else ""
    if not origin:
        raise DomainError("ORIGIN_FORBIDDEN", "缺少 Origin 请求头", "从 http://127.0.0.1:%d 页面发起请求" % port, 403)
    if not origin_allowed(origin, port):
        raise DomainError("ORIGIN_FORBIDDEN", "跨源请求被拒绝", "从 http://127.0.0.1:%d 页面发起请求" % port, 403)


def _cookie_token(handler) -> Optional[str]:
    raw = handler.headers.get("Cookie", "") if handler.headers else ""
    if not raw:
        return None
    jar = SimpleCookie()
    try:
        jar.load(raw)
    except Exception:
        return None
    morsel = jar.get(COOKIE_NAME)
    return morsel.value if morsel else None


def authenticate(handler, token: SessionToken) -> None:
    header = handler.headers.get(HEADER_NAME, "") if handler.headers else ""
    candidate = header or _cookie_token(handler)
    if not token.verify(candidate):
        raise DomainError("UNAUTHENTICATED", "缺少或无效的会话令牌", "刷新页面获取新 token，或在头中携带 X-Skillmerge-Token", 401)


def parse_json(body: bytes) -> Dict[str, Any]:
    if not body:
        return {}
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise DomainError("BAD_REQUEST", "请求体不是合法 JSON", "检查 JSON 语法与 UTF-8 编码")
    if not isinstance(value, dict):
        raise DomainError("BAD_REQUEST", "请求体必须是 JSON 对象", "提交 {...} 结构")
    return value