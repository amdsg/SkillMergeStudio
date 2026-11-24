from __future__ import annotations

from typing import Any, Dict, Optional


class BrowserSession:
    def goto(self, url: str) -> None:  # pragma: no cover - 协议
        raise NotImplementedError

    def eval(self, script: str) -> Any:  # pragma: no cover - 协议
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - 协议
        raise NotImplementedError


def _playwright() -> Optional[Any]:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore

        return sync_playwright()
    except Exception:
        return None


def _selenium() -> Optional[Any]:
    try:
        import selenium  # type: ignore

        return selenium
    except Exception:
        return None


def detect_backend() -> Optional[str]:
    """默认关闭：未安装任何浏览器开发依赖时返回 None。"""
    if _playwright() is not None:
        return "playwright"
    if _selenium() is not None:
        return "selenium"
    return None


def backend_capabilities(backend: Optional[str]) -> Dict[str, Any]:
    return {
        "backend": backend,
        "auto_dom": backend == "playwright",
        "cls_observer": backend == "playwright",
        "reason": "" if backend else "Q-32 未批准：浏览器开发依赖未安装",
    }