"""Typed application errors and the public error response model.

Every error surfaced to a client uses the shape::

    {"error": {"code": "SOURCE_UNSUPPORTED", "message": "...", "retryable": false}}

Error codes are stable identifiers that the frontend maps to localized text.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    # Input / validation
    INVALID_URL = "INVALID_URL"
    URL_TOO_LONG = "URL_TOO_LONG"
    UNSUPPORTED_SCHEME = "UNSUPPORTED_SCHEME"
    BLOCKED_TARGET = "BLOCKED_TARGET"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_OPTIONS = "INVALID_OPTIONS"

    # Source / fetch
    SOURCE_UNREACHABLE = "SOURCE_UNREACHABLE"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    SOURCE_FORBIDDEN = "SOURCE_FORBIDDEN"
    SOURCE_TIMEOUT = "SOURCE_TIMEOUT"
    SOURCE_TOO_LARGE = "SOURCE_TOO_LARGE"
    SOURCE_UNSUPPORTED = "SOURCE_UNSUPPORTED"
    SOURCE_REQUIRES_AUTH = "SOURCE_REQUIRES_AUTH"
    SOURCE_DRM_PROTECTED = "SOURCE_DRM_PROTECTED"
    SOURCE_GEO_RESTRICTED = "SOURCE_GEO_RESTRICTED"
    SOURCE_LIVE_STREAM = "SOURCE_LIVE_STREAM"
    SOURCE_PRIVATE = "SOURCE_PRIVATE"
    SOURCE_INVALID_CONTENT = "SOURCE_INVALID_CONTENT"
    TOO_MANY_REDIRECTS = "TOO_MANY_REDIRECTS"

    # Files / processing
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    FILE_TYPE_UNSUPPORTED = "FILE_TYPE_UNSUPPORTED"
    FILE_CORRUPT = "FILE_CORRUPT"
    FORMAT_UNAVAILABLE = "FORMAT_UNAVAILABLE"
    PAGE_LIMIT_EXCEEDED = "PAGE_LIMIT_EXCEEDED"
    PROCESSING_FAILED = "PROCESSING_FAILED"
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"
    TOOL_UNAVAILABLE = "TOOL_UNAVAILABLE"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    TOOL_INPUT_MISMATCH = "TOOL_INPUT_MISMATCH"

    # Jobs
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    JOB_NOT_READY = "JOB_NOT_READY"
    JOB_EXPIRED = "JOB_EXPIRED"
    JOB_CANCELLED = "JOB_CANCELLED"
    JOB_NOT_CANCELLABLE = "JOB_NOT_CANCELLABLE"
    QUEUE_FULL = "QUEUE_FULL"
    STORAGE_FULL = "STORAGE_FULL"
    UPLOAD_NOT_FOUND = "UPLOAD_NOT_FOUND"

    # Platform / infra
    RATE_LIMITED = "RATE_LIMITED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


_DEFAULT_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_URL: 400,
    ErrorCode.URL_TOO_LONG: 414,
    ErrorCode.UNSUPPORTED_SCHEME: 400,
    ErrorCode.BLOCKED_TARGET: 400,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.INVALID_OPTIONS: 422,
    ErrorCode.SOURCE_UNREACHABLE: 502,
    ErrorCode.SOURCE_NOT_FOUND: 404,
    ErrorCode.SOURCE_FORBIDDEN: 403,
    ErrorCode.SOURCE_TIMEOUT: 504,
    ErrorCode.SOURCE_TOO_LARGE: 413,
    ErrorCode.SOURCE_UNSUPPORTED: 422,
    ErrorCode.SOURCE_REQUIRES_AUTH: 422,
    ErrorCode.SOURCE_DRM_PROTECTED: 422,
    ErrorCode.SOURCE_GEO_RESTRICTED: 422,
    ErrorCode.SOURCE_LIVE_STREAM: 422,
    ErrorCode.SOURCE_PRIVATE: 422,
    ErrorCode.SOURCE_INVALID_CONTENT: 422,
    ErrorCode.TOO_MANY_REDIRECTS: 422,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.FILE_TYPE_UNSUPPORTED: 415,
    ErrorCode.FILE_CORRUPT: 422,
    ErrorCode.FORMAT_UNAVAILABLE: 422,
    ErrorCode.PAGE_LIMIT_EXCEEDED: 422,
    ErrorCode.PROCESSING_FAILED: 500,
    ErrorCode.PROCESSING_TIMEOUT: 504,
    ErrorCode.TOOL_UNAVAILABLE: 503,
    ErrorCode.TOOL_NOT_FOUND: 404,
    ErrorCode.TOOL_INPUT_MISMATCH: 422,
    ErrorCode.JOB_NOT_FOUND: 404,
    ErrorCode.JOB_NOT_READY: 409,
    ErrorCode.JOB_EXPIRED: 410,
    ErrorCode.JOB_CANCELLED: 409,
    ErrorCode.JOB_NOT_CANCELLABLE: 409,
    ErrorCode.QUEUE_FULL: 503,
    ErrorCode.STORAGE_FULL: 503,
    ErrorCode.UPLOAD_NOT_FOUND: 404,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.INTERNAL_ERROR: 500,
}

_RETRYABLE: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.SOURCE_UNREACHABLE,
        ErrorCode.SOURCE_TIMEOUT,
        ErrorCode.PROCESSING_TIMEOUT,
        ErrorCode.QUEUE_FULL,
        ErrorCode.STORAGE_FULL,
        ErrorCode.RATE_LIMITED,
        ErrorCode.SERVICE_UNAVAILABLE,
        ErrorCode.INTERNAL_ERROR,
    }
)


class AppError(Exception):
    """Base class for all errors that may be surfaced to the client."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool | None = None,
        details: dict[str, Any] | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code if status_code is not None else _DEFAULT_STATUS[code]
        self.retryable = retryable if retryable is not None else code in _RETRYABLE
        self.details = details or {}
        self.retry_after = retry_after

    def to_payload(self) -> ErrorPayload:
        return ErrorPayload(
            code=self.code,
            message=self.message,
            retryable=self.retryable,
            details=self.details or None,
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"AppError({self.code}, {self.message!r})"


class ErrorPayload(BaseModel):
    code: ErrorCode
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorPayload = Field(..., description="Structured error description.")
