from __future__ import annotations

from typing import Any, Dict, Optional


class DomainError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        fix: str = "",
        status: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix or "请查看接口文档并修正请求参数。"
        self.status = status
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "fix": self.fix,
            "details": self.details,
        }

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class CancelledError(Exception):
    pass


def bad_request(message: str, fix: str = "") -> DomainError:
    return DomainError("BAD_REQUEST", message, fix, 400)


def not_found(message: str, fix: str = "") -> DomainError:
    return DomainError("NOT_FOUND", message, fix, 404)