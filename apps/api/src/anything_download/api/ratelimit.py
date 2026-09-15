"""IP based fixed-window rate limiting.

Counters live in Redis (shared across API replicas). If Redis is unreachable
the limiter falls back to an in-process window so abuse protection degrades
gracefully instead of disappearing.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

import redis.asyncio as aioredis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from anything_download.api.state import client_ip
from anything_download.config import Settings
from anything_download.errors import ErrorCode, ErrorPayload, ErrorResponse
from anything_download.logging import get_logger

log = get_logger(__name__)

WINDOW_SECONDS = 60


@dataclass(frozen=True)
class Bucket:
    name: str
    limit: int


class RateLimiter:
    def __init__(self, redis: aioredis.Redis, settings: Settings) -> None:
        self.redis = redis
        self.settings = settings
        self._memory: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def bucket_for(self, method: str, path: str) -> Bucket:
        s = self.settings
        if method == "POST" and path.endswith("/analyze"):
            return Bucket("analyze", s.rate_limit_analyze_per_minute)
        if method == "POST" and path.endswith("/jobs"):
            return Bucket("jobs", s.rate_limit_jobs_per_minute)
        if method == "POST" and path.endswith("/uploads"):
            return Bucket("uploads", s.rate_limit_uploads_per_minute)
        return Bucket("general", s.rate_limit_general_per_minute)

    async def hit(self, ip: str, bucket: Bucket) -> tuple[bool, int, int]:
        """Register a request. Returns (allowed, remaining, retry_after_seconds)."""
        now = int(time.time())
        window = now // WINDOW_SECONDS
        key = f"ad:ratelimit:{bucket.name}:{ip}:{window}"
        reset_in = WINDOW_SECONDS - (now % WINDOW_SECONDS)
        try:
            pipe = self.redis.pipeline(transaction=True)
            pipe.incr(key)
            pipe.expire(key, WINDOW_SECONDS + 1)
            count_raw, _ = await pipe.execute()
            count = int(count_raw)
        except (RedisError, OSError):
            count = self._memory_hit(key, window)
        allowed = count <= bucket.limit
        return allowed, max(0, bucket.limit - count), reset_in

    def _memory_hit(self, key: str, window: int) -> int:
        stored_window, count = self._memory[key]
        if stored_window != window:
            count = 0
        count += 1
        self._memory[key] = (window, count)
        if len(self._memory) > 50_000:  # crude bound to avoid unbounded growth
            self._memory.clear()
        return count


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: RateLimiter) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.limiter = limiter

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        settings = self.limiter.settings
        path = request.url.path
        if (
            not settings.rate_limit_enabled
            or not path.startswith("/api/")
            or path.endswith(("/health", "/ready"))
        ):
            return await call_next(request)
        ip = client_ip(request, settings)
        bucket = self.limiter.bucket_for(request.method, path)
        allowed, remaining, reset_in = await self.limiter.hit(ip, bucket)
        if not allowed:
            payload = ErrorResponse(
                error=ErrorPayload(
                    code=ErrorCode.RATE_LIMITED,
                    message="Too many requests. Please try again later.",
                    retryable=True,
                )
            )
            return JSONResponse(
                payload.model_dump(),
                status_code=429,
                headers={
                    "Retry-After": str(reset_in),
                    "X-RateLimit-Limit": str(bucket.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(bucket.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
