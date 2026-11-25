"""只读 GitHub 客户端：端点白名单、内存 Token、稳定错误码。

仅依赖标准库 urllib，Token 只保存在进程内存中，绝不进入 repr / health / 日志。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NoReturn

from ...util.errors import DomainError

REGISTRY = Path(__file__).resolve().parent / "endpoint_registry.json"
DEFAULT_BASE = "https://api.github.com"
USER_AGENT = "skill-merge-studio/1.0"


def load_endpoints() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8")).get("endpoints", [])


def match_endpoint(method: str, path: str) -> dict | None:
    for endpoint in load_endpoints():
        if endpoint.get("method") != method.upper():
            continue
        if re.match(endpoint.get("pattern", ""), path):
            return endpoint
    return None


def _transport(method: str, url: str, headers: dict):
    request = urllib.request.Request(url, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()
    except urllib.error.URLError as error:
        reason = str(getattr(error, "reason", error))[:120]
        raise DomainError("GITHUB_NETWORK", f"无法连接 GitHub：{reason}", "检查网络后重试", 502) from error


class GithubClient:
    """只读客户端：Token 仅在内存，绝不写入日志或返回体。"""

    def __init__(self, token: str = "", transport=None, base_url: str = DEFAULT_BASE) -> None:
        self._token = str(token or "")
        self._transport = transport or _transport
        self._base = base_url.rstrip("/")
        self.calls = 0

    @property
    def mode(self) -> str:
        return "authenticated" if self._token else "anonymous"

    def health(self) -> dict:
        return {"mode": self.mode, "endpoints": len(load_endpoints()), "writes_allowed": False}

    def request(self, method: str, path: str, params: dict | None = None) -> dict:
        method = method.upper()
        if method not in ("GET", "HEAD"):
            raise DomainError("GITHUB_WRITE_FORBIDDEN", "GitHub 客户端仅支持只读", "使用只读操作", 403)
        endpoint = match_endpoint(method, path)
        if endpoint is None:
            raise DomainError("GITHUB_ENDPOINT_DENIED", f"端点未授权：{path}", "仅使用白名单端点", 403)
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self._base}{path}{query}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self.calls += 1
        status, response_headers, body = self._transport(method, url, headers)
        meta = self._meta(status, response_headers)
        if status in (200, 201):
            try:
                data = json.loads(body.decode("utf-8")) if body else {}
            except ValueError as error:
                raise DomainError("GITHUB_UPSTREAM", "GitHub 返回非 JSON", "稍后重试", 502) from error
            return {"ok": True, "data": data, "meta": meta, "endpoint": endpoint.get("id")}
        self._raise_for_status(status, response_headers)

    def _meta(self, status: int, headers: dict) -> dict:
        remaining = headers.get("x-ratelimit-remaining", "unknown")
        reset = headers.get("x-ratelimit-reset", "unknown")
        retry_after = headers.get("retry-after", "")
        return {
            "status": status,
            "remaining": remaining,
            "reset_at": reset,
            "retry_after_seconds": int(retry_after) if str(retry_after).isdigit() else "unknown",
            "mode": self.mode,
        }

    def _raise_for_status(self, status: int, headers: dict) -> NoReturn:
        meta = self._meta(status, headers)
        if status == 401:
            raise DomainError("GITHUB_AUTH_INVALID", "GitHub Token 无效", "在设置中重新填写 Token", 401)
        if status in (403, 429) and meta.get("remaining") == "0":
            raise DomainError("GITHUB_RATE_LIMIT", "GitHub 请求限额已用尽", "稍后重试或在设置中配置 Token", 429)
        if status == 403:
            raise DomainError("GITHUB_FORBIDDEN", "GitHub 拒绝访问", "检查 Token 或权限", 403)
        if status == 404:
            raise DomainError("GITHUB_NOT_FOUND", "GitHub 资源不存在", "检查仓库名是否正确", 404)
        raise DomainError("GITHUB_UPSTREAM", f"GitHub 返回错误 {status}", "稍后重试", 502)

    def download(self, path: str, params: dict | None = None) -> bytes:
        """下载原始字节流（如 zipball），不做 JSON 解析。"""
        endpoint = match_endpoint("GET", path)
        if endpoint is None:
            raise DomainError("GITHUB_ENDPOINT_DENIED", f"端点未授权：{path}", "仅使用白名单端点", 403)
        query = f"?{urllib.parse.urlencode(params)}" if params else ""
        url = f"{self._base}{path}{query}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self.calls += 1
        status, response_headers, body = self._transport("GET", url, headers)
        if status in (200, 201):
            return body
        self._raise_for_status(status, response_headers)
