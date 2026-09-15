"""FastAPI application factory."""

from __future__ import annotations

import contextlib
import uuid
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from anything_download import __version__
from anything_download.api.limits import RequestBodyLimitMiddleware
from anything_download.api.ratelimit import RateLimiter, RateLimitMiddleware
from anything_download.api.routes import analyze, jobs, meta, uploads
from anything_download.api.state import AppState
from anything_download.config import Settings, get_settings
from anything_download.errors import AppError, ErrorCode, ErrorPayload, ErrorResponse
from anything_download.jobs.store import JobStore
from anything_download.logging import configure_logging, get_logger
from anything_download.net.client import SafeHttpClient
from anything_download.storage.local import LocalStorage
from anything_download.tools.registry import load_all

log = get_logger(__name__)

API_PREFIX = "/api/v1"

_DESCRIPTION = """
Anything Download analyzes publicly accessible URLs and files and performs
download, conversion, compression and extraction operations.

* No account is required.
* Results are temporary and deleted automatically.
* Only content the user is authorized to access is processed: the service does
  not bypass authentication, DRM, paywalls or other access controls.
"""


def create_app(
    settings: Settings | None = None, *, redis_client: aioredis.Redis | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        redis = redis_client or aioredis.Redis.from_url(settings.redis_url)
        storage = LocalStorage(settings=settings)
        storage.ensure_dirs()
        load_all()
        state = AppState(
            settings=settings,
            redis=redis,
            store=JobStore(redis, settings),
            storage=storage,
            http=SafeHttpClient(settings, max_bytes=settings.max_webpage_bytes * 4),
        )
        app.state.ad = state
        limiter.redis = redis
        log.info("api.started", env=settings.env, version=__version__)
        try:
            yield
        finally:
            await state.http.aclose()
            if redis_client is None:
                await redis.aclose()
            log.info("api.stopped")

    app = FastAPI(
        title="Anything Download API",
        version=__version__,
        description=_DESCRIPTION.strip(),
        lifespan=lifespan,
        docs_url=f"{API_PREFIX}/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if settings.enable_docs else None,
        root_path=settings.api_root_path,
        responses={500: {"model": ErrorResponse}},
    )

    # Placeholder Redis client; replaced in lifespan (needed so middleware can be built eagerly).
    limiter = RateLimiter(redis_client or aioredis.Redis.from_url(settings.redis_url), settings)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-File-Name", "X-File-Type", "X-Request-ID"],
        expose_headers=[
            "Content-Disposition",
            "Retry-After",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-Request-ID",
        ],
        max_age=600,
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next: Any) -> Any:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id[:64])
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id[:64]
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    # Added last so it runs first: oversized bodies are refused before rate limiting
    # or any route touches them.
    app.add_middleware(
        RequestBodyLimitMiddleware,
        max_bytes=settings.max_request_body_kb * 1024,
        exempt_paths=frozenset({f"{API_PREFIX}/uploads"}),
    )

    _register_error_handlers(app, settings)

    app.include_router(analyze.router, prefix=API_PREFIX)
    app.include_router(jobs.router, prefix=API_PREFIX)
    app.include_router(uploads.router, prefix=API_PREFIX)
    app.include_router(meta.router, prefix=API_PREFIX)
    return app


def _error_response(exc: AppError) -> JSONResponse:
    headers = {}
    if exc.retry_after:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        ErrorResponse(error=exc.to_payload()).model_dump(exclude_none=True),
        status_code=exc.status_code,
        headers=headers,
    )


def _register_error_handlers(app: FastAPI, settings: Settings) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg", "")}
            for e in exc.errors()
        ]
        return _error_response(
            AppError(
                ErrorCode.VALIDATION_ERROR, "The request is not valid.", details={"errors": details}
            )
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            404: ErrorCode.TOOL_NOT_FOUND,
            405: ErrorCode.VALIDATION_ERROR,
            413: ErrorCode.FILE_TOO_LARGE,
        }.get(exc.status_code, ErrorCode.VALIDATION_ERROR)
        if exc.status_code == 404:
            message = "Not found."
        elif exc.status_code >= 500:
            code, message = ErrorCode.INTERNAL_ERROR, "Internal server error."
        else:
            message = str(exc.detail) if exc.detail else "Request error."
        payload = ErrorResponse(
            error=ErrorPayload(code=code, message=message, retryable=exc.status_code >= 500)
        )
        return JSONResponse(payload.model_dump(exclude_none=True), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
        log.exception("api.unhandled", error=type(exc).__name__)
        message = (
            "An unexpected error occurred."
            if settings.is_production
            else f"{type(exc).__name__}: {exc}"
        )
        return _error_response(AppError(ErrorCode.INTERNAL_ERROR, message))
