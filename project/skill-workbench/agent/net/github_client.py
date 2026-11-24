"""Read-only GitHub client: endpoint allowlist, in-memory token, stable error codes."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NoReturn

from agent.http.errors import DomainError

REGISTRY = Path(__file__).resolve().parent / "endpoint_registry.json"
DEFAULT_BASE = "https://api.github.com"
USER_AGENT = "skill-workbench/1.0"


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
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, {k.lower(): v for k, v in response.headers.items()}, response.read()
    except urllib.error.HTTPError as error:
        return error.code, {k.lower(): v for k, v in error.headers.items()}, error.read()
    except urllib.error.URLError as error:
        raise DomainError("E_GITHUB_NETWORK", "wb.error.github_network",
                          params={"reason": str(error.reason)[:120]}, fix_key="wb.fix.retry_later") from error


class GithubClient:
    """Token stays in process memory only and never appears in repr or health."""

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
            raise DomainError("E_GITHUB_WRITE_FORBIDDEN", "wb.error.github_write_forbidden",
                              params={"method": method}, fix_key="wb.fix.use_read_only")
        endpoint = match_endpoint(method, path)
        if endpoint is None:
            raise DomainError("E_GITHUB_ENDPOINT_DENIED", "wb.error.github_endpoint_denied",
                              params={"path": path}, fix_key="wb.fix.use_read_only")
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
                raise DomainError("E_GITHUB_UPSTREAM", "wb.error.github_upstream",
                                  params={"status": status}, fix_key="wb.fix.retry_later") from error
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
            raise DomainError("E_GITHUB_AUTH_INVALID", "wb.error.github_auth_invalid",
                              params=meta, fix_key="wb.fix.check_token")
        if status in (403, 429) and meta.get("remaining") == "0":
            raise DomainError("E_GITHUB_RATE_LIMIT", "wb.error.github_rate_limit",
                              params=meta, fix_key="wb.fix.retry_later")
        if status == 403:
            raise DomainError("E_GITHUB_FORBIDDEN", "wb.error.github_forbidden",
                              params=meta, fix_key="wb.fix.check_token")
        if status == 404:
            raise DomainError("E_GITHUB_NOT_FOUND", "wb.error.github_not_found",
                              params=meta, fix_key="wb.fix.check_repo")
        raise DomainError("E_GITHUB_UPSTREAM", "wb.error.github_upstream",
                          params={"status": status}, fix_key="wb.fix.retry_later")

    def download(self, path: str, params: dict | None = None) -> bytes:
        endpoint = match_endpoint("GET", path)
        if endpoint is None:
            raise DomainError("E_GITHUB_ENDPOINT_DENIED", "wb.error.github_endpoint_denied",
                              params={"path": path}, fix_key="wb.fix.use_read_only")
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