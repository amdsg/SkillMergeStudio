from __future__ import annotations

import os
from typing import Dict, Optional


from ..security import SessionToken
from ..util.errors import DomainError
from .response import send_bytes

MIME = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}


def _within(target: str, root: str) -> bool:
    try:
        target_real = os.path.realpath(os.path.abspath(target))
        root_real = os.path.realpath(os.path.abspath(root))
        return os.path.commonpath([target_real, root_real]) == root_real
    except ValueError:
        return False


def _resolve(web_root: str, path: str) -> Optional[str]:
    if path in ("/", "/index.html"):
        relative = "index.html"
    elif path == "/favicon.ico":
        relative = "favicon.ico"
    elif path.startswith("/assets/"):
        relative = path.lstrip("/")
    elif path.startswith("/css/") or path.startswith("/js/"):
        relative = path.lstrip("/")
    else:
        return None
    if ".." in relative.split("/"):
        raise DomainError("PATH_OUT_OF_BOUNDS", "静态资源路径非法", "使用页面内的正常链接", 400)
    target = os.path.join(web_root, relative.replace("/", os.sep))
    if not _within(target, web_root):
        raise DomainError("PATH_OUT_OF_BOUNDS", "静态资源越界", "使用页面内的正常链接", 400)
    if not os.path.isfile(target):
        return None
    return target


def serve_static(handler, path: str, web_root: str, token: SessionToken) -> bool:
    target = _resolve(web_root, path)
    if target is None:
        return False
    extension = os.path.splitext(target)[1].lower()
    content_type = MIME.get(extension)
    if content_type is None:
        raise DomainError("NOT_FOUND", "静态资源类型不允许", "仅访问页面自带资源", 404)
    try:
        with open(target, "rb") as handle:
            body = handle.read()
    except OSError:
        raise DomainError("NOT_FOUND", "静态资源不存在", "刷新页面或重新安装程序", 404)
    extra: Dict[str, str] = {}
    if path in ("/", "/index.html"):
        extra["Set-Cookie"] = token.cookie()
    send_bytes(handler, 200, body, content_type, extra)
    return True