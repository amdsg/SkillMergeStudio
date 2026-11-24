from __future__ import annotations

import hmac
import ipaddress
import secrets
from typing import Optional
from urllib.parse import urlsplit

COOKIE_NAME = "sms_session"
HEADER_NAME = "X-Skillmerge-Token"
CSRF_HEADER = "X-Skillmerge"


class SessionToken:
    def __init__(self, value: Optional[str] = None) -> None:
        self.value = value or secrets.token_hex(32)

    def verify(self, candidate: Optional[str]) -> bool:
        if not candidate:
            return False
        return hmac.compare_digest(str(candidate), self.value)

    def cookie(self) -> str:
        return f"{COOKIE_NAME}={self.value}; Path=/; HttpOnly; SameSite=Strict"


def _host_without_port(host: str) -> str:
    value = host.strip()
    if value.startswith("["):
        return value.split("]", 1)[0] + "]"
    return value.rsplit(":", 1)[0] if ":" in value else value


def host_allowed(host_header: str, port: int) -> bool:
    if not host_header:
        return False
    value = host_header.strip().lower()
    allowed = {
        f"127.0.0.1:{port}",
        f"localhost:{port}",
        f"[::1]:{port}",
        "127.0.0.1",
        "localhost",
        "[::1]",
    }
    if value in allowed:
        return True
    host = _host_without_port(value)
    if host in ("127.0.0.1", "localhost", "[::1]"):
        return value == host or value.endswith(f":{port}")
    return False


def origin_allowed(origin: Optional[str], port: int) -> bool:
    if not origin:
        return False
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    if parsed.scheme != "http":
        return False
    try:
        host = parsed.hostname or ""
    except ValueError:
        return False
    if parsed.port not in (None, port):
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def redact(text: str) -> str:
    from .util.logging import redact as _redact

    return _redact(text)


def mask_key(value: str) -> str:
    return "***" if value else ""