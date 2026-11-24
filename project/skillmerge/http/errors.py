from __future__ import annotations

from typing import Dict, Tuple

from ..util.errors import DomainError

CODE_STATUS: Dict[str, int] = {
    "BAD_REQUEST": 400,
    "INVALID_ARGUMENT": 400,
    "PATH_OUT_OF_BOUNDS": 400,
    "MISSING_CSRF_HEADER": 400,
    "HEADERS_TOO_LARGE": 400,
    "UNAUTHENTICATED": 401,
    "ORIGIN_FORBIDDEN": 403,
    "HOST_FORBIDDEN": 403,
    "NOT_FOUND": 404,
    "METHOD_NOT_ALLOWED": 405,
    "JOB_STATE_CONFLICT": 409,
    "ARTIFACT_MODIFIED": 409,
    "PAYLOAD_TOO_LARGE": 413,
    "QUEUE_FULL": 429,
    "EXPORT_BLOCKED": 466,
    "INTERNAL_ERROR": 500,
    "STORAGE_ERROR": 500,
}


def status_for(error: DomainError) -> int:
    if error.status and error.status != 400:
        return int(error.status)
    return CODE_STATUS.get(error.code, int(error.status or 400))


def error_payload(error: DomainError) -> Dict[str, object]:
    return {"code": error.code, "message": error.message, "fix": error.fix or "请检查请求后重试"}


def internal_error() -> DomainError:
    return DomainError("INTERNAL_ERROR", "服务内部错误", "查看 stderr 日志中的 request_id 后重试", 500)