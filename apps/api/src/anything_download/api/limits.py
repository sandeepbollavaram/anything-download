"""Request body size limit for every endpoint except the streaming upload.

FastAPI reads JSON bodies fully into memory, so without a cap one request to
``/analyze`` or ``/jobs`` could allocate as much memory as the proxy lets through.
A declared ``Content-Length`` over the limit is refused without reading. A body with
no declared length (chunked) is read here, up to the limit, and replayed to the app;
crossing the limit is refused with 413. Buffering is bounded by the same small limit.

The body is read here rather than counted inside the app's ``receive`` because
FastAPI turns any exception raised while it parses a body into a generic 400.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from anything_download.errors import AppError, ErrorCode


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int, exempt_paths: frozenset[str]) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.exempt_paths = exempt_paths

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") in self.exempt_paths:
            await self.app(scope, receive, send)
            return

        declared = _content_length(scope)
        if declared is not None and declared > self.max_bytes:
            await self._refuse(scope, receive, send)
            return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                # Client went away before sending the whole body; let the app see it.
                await self.app(scope, _replay([message]), send)
                return
            body = message.get("body", b"")
            size += len(body)
            if size > self.max_bytes:
                await self._refuse(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        buffered: Message = {"type": "http.request", "body": b"".join(chunks), "more_body": False}
        await self.app(scope, _replay([buffered], then=receive), send)

    async def _refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        from anything_download.api.app import _error_response

        error = AppError(
            ErrorCode.FILE_TOO_LARGE,
            f"The request body is too large (limit {max(1, self.max_bytes // 1024)} KB).",
        )
        await _error_response(error)(scope, receive, send)


def _replay(messages: list[Message], then: Receive | None = None) -> Receive:
    pending = list(messages)

    async def receive() -> Message:
        if pending:
            return pending.pop(0)
        if then is not None:
            return await then()  # after the body: e.g. http.disconnect
        return {"type": "http.disconnect"}

    return receive


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None
