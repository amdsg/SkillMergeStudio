"""Request guards: local origin, CSRF header and optional bearer token."""
from __future__ import annotations

import re

LOCAL_ORIGIN = re.compile(r"^http://(127\.0\.0\.1|localhost)(:\d+)?$")
EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[a-z]{32}$")
PAIR_TOKEN = ""


def set_pair_token(token: str) -> None:
    global PAIR_TOKEN
    PAIR_TOKEN = token


def origin_allowed(origin: str) -> bool:
    if not origin:
        return True
    return bool(LOCAL_ORIGIN.match(origin) or EXTENSION_ORIGIN.match(origin))


def write_allowed(method: str, headers) -> bool:
    if method.upper() in ("GET", "HEAD", "OPTIONS"):
        return True
    return headers.get("X-WB-CSRF", "") == "1"