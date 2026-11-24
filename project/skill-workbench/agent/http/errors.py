"""Unified error type and payload shape. Codes stay English constants."""
from __future__ import annotations

ERROR_STATUS = {
    "E_BAD_REQUEST": 400,
    "E_TOKEN_INVALID": 401,
    "E_ORIGIN_DENIED": 403,
    "E_APPLICABILITY_ACK_REQUIRED": 403,
    "E_CAPABILITY_DISABLED": 403,
    "E_RISK_ACK_REQUIRED": 403,
    "E_CONFIRM_REQUIRED": 403,
    "E_NOT_FOUND": 404,
    "E_TARGET_CHANGED": 409,
    "E_INTERMEDIATE_INVALID": 400,
    "E_INTERMEDIATE_REQUIRED": 409,
    "E_INTERMEDIATE_SCHEMA_TOO_OLD": 409,
    "E_PLAN_STALE": 409,
    "E_REF_INCOMPLETE": 409,
    "E_TARGET_NOT_REGISTERED": 409,
    "E_SOURCE_NOT_DOWNLOADED": 409,
    "E_ARCHIVE_TOO_LARGE": 413,
    "E_UNSUPPORTED_BINARY": 415,
    "E_APPLICABILITY_UNKNOWN": 422,
    "E_JOB_BUSY": 429,
    "E_GITHUB_RATE_LIMIT": 429,
    "E_GITHUB_WRITE_FORBIDDEN": 403,
    "E_GITHUB_ENDPOINT_DENIED": 403,
    "E_GITHUB_AUTH_INVALID": 401,
    "E_GITHUB_FORBIDDEN": 403,
    "E_GITHUB_UPSTREAM": 502,
    "E_GITHUB_NETWORK": 503,
    "E_PATH_DENIED": 403,
    "E_PAIR_CODE_INVALID": 401,
    "E_PAIR_CODE_USED": 401,
    "E_PAIR_CODE_EXPIRED": 401,
    "E_DEPENDENCY_SOURCE_DENIED": 403,
    "E_WRITE_FAILED": 500,
    "E_TARGET_REGISTRY_INVALID": 500,
    "E_TARGET_UNKNOWN": 422,
    "E_TOOL_EVIDENCE_MISSING": 422,
    "E_BACKUP_FAILED": 500,
    "E_ROLLBACK_FAILED": 500,
    "E_ENGINE_UNAVAILABLE": 503,
    "E_ENGINE_VERSION": 503,
    "E_ENGINE_AUTH": 503,
    "E_INTERNAL": 500,
}


class DomainError(Exception):
    """Stable machine-readable error with message_key and fix_key."""

    def __init__(self, code: str, message_key: str, status: int | None = None,
                 params: dict | None = None, fix_key: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.message_key = message_key
        self.status = status if status is not None else ERROR_STATUS.get(code, 400)
        self.params = params or {}
        self.fix_key = fix_key

    def payload(self) -> dict:
        return {
            "ok": False,
            "error": {
                "code": self.code,
                "message_key": self.message_key,
                "params": self.params,
                "fix_key": self.fix_key,
            },
        }