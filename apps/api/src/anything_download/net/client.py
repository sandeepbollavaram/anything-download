"""SSRF-hardened HTTP client.

Every outbound request goes through :class:`SafeHttpClient`, which

* validates and resolves the target with :func:`validate_and_resolve`,
* connects to the *validated IP address* (the URL host is swapped for the IP,
  the original host is sent via ``Host`` / SNI) so a DNS answer cannot change
  between validation and connection (DNS rebinding),
* follows redirects manually, re-validating every hop,
* enforces size limits while streaming, never buffering whole files,
* disables connection reuse so a pinned TLS session is never shared between
  different host names that resolve to the same IP.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from types import TracebackType
from typing import Any, Self
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx

from anything_download.config import Settings, get_settings
from anything_download.errors import AppError, ErrorCode
from anything_download.logging import get_logger
from anything_download.security.urls import ValidatedURL, validate_and_resolve

log = get_logger(__name__)

_REDIRECT_CODES = {301, 302, 303, 307, 308}


@dataclass
class SafeResponse:
    """A streamed response bound to the validated final URL."""

    status_code: int
    headers: httpx.Headers
    final_url: ValidatedURL
    redirects: int
    _response: httpx.Response
    _max_bytes: int

    @property
    def content_type(self) -> str | None:
        value = self.headers.get("content-type")
        return str(value) if value is not None else None

    @property
    def content_length(self) -> int | None:
        """Declared body size, or None when unknown or when the body is content-encoded."""
        encoding = (self.headers.get("content-encoding") or "identity").lower()
        if encoding not in {"identity", ""}:
            return None
        raw = self.headers.get("content-length")
        if raw is None:
            return None
        try:
            value = int(raw)
        except ValueError:
            return None
        return value if value >= 0 else None

    @property
    def content_disposition(self) -> str | None:
        value = self.headers.get("content-disposition")
        return str(value) if value is not None else None

    _iterator: AsyncIterator[bytes] | None = None
    _pending: bytes = b""
    _received: int = 0

    def _stream(self) -> AsyncIterator[bytes]:
        if self._iterator is None:
            self._iterator = self._response.aiter_bytes(64 * 1024)
        return self._iterator

    async def _next_chunk(self) -> bytes | None:
        try:
            return await self._stream().__anext__()
        except StopAsyncIteration:
            return None
        except httpx.TimeoutException as exc:
            raise AppError(
                ErrorCode.SOURCE_TIMEOUT, "The source stopped responding while downloading."
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                ErrorCode.SOURCE_UNREACHABLE, "The connection to the source was interrupted."
            ) from exc

    def _account(self, chunk: bytes) -> None:
        self._received += len(chunk)
        if self._received > self._max_bytes:
            raise AppError(
                ErrorCode.SOURCE_TOO_LARGE,
                f"The file exceeds the maximum allowed size of {self._max_bytes // (1024 * 1024)} MB.",
            )

    async def aiter_bytes(self) -> AsyncIterator[bytes]:
        """Yield the remaining body (after anything consumed by :meth:`read_limited`)."""
        if self._pending:
            pending, self._pending = self._pending, b""
            yield pending
        while True:
            chunk = await self._next_chunk()
            if chunk is None:
                return
            self._account(chunk)
            yield chunk

    async def read_limited(self, limit: int) -> bytes:
        """Read up to ``limit`` bytes without consuming more of the stream than needed.

        Bytes read here are *also* re-emitted by a subsequent :meth:`aiter_bytes`
        call, so callers can sniff a file head and then stream the whole body.
        """
        buf = bytearray(self._pending)
        self._pending = b""
        while len(buf) < limit:
            chunk = await self._next_chunk()
            if chunk is None:
                break
            self._account(chunk)
            buf.extend(chunk)
        head = bytes(buf[:limit])
        self._pending = bytes(buf)
        return head

    async def read_all(self, limit: int) -> tuple[bytes, bool]:
        """Read the body up to ``limit`` bytes. Returns (data, truncated)."""
        buf = bytearray()
        truncated = False
        async for chunk in self.aiter_bytes():
            buf.extend(chunk)
            if len(buf) > limit:
                truncated = True
                del buf[limit:]
                break
        return bytes(buf), truncated

    async def aclose(self) -> None:
        await self._response.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()


class SafeHttpClient:
    def __init__(self, settings: Settings | None = None, *, max_bytes: int | None = None) -> None:
        self.settings = settings or get_settings()
        self.max_bytes = max_bytes or self.settings.max_file_size_bytes
        self._client = httpx.AsyncClient(
            follow_redirects=False,
            http2=False,
            timeout=httpx.Timeout(
                connect=self.settings.http_connect_timeout_seconds,
                read=self.settings.http_read_timeout_seconds,
                write=self.settings.http_read_timeout_seconds,
                pool=self.settings.http_connect_timeout_seconds,
            ),
            limits=httpx.Limits(max_keepalive_connections=0, max_connections=20),
            headers={
                "User-Agent": self.settings.user_agent,
                "Accept": "*/*",
                "Accept-Language": "en",
            },
            trust_env=False,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    async def get(
        self,
        url: str | ValidatedURL,
        *,
        headers: Mapping[str, str] | None = None,
        accept_encoding_identity: bool = True,
    ) -> SafeResponse:
        """Perform a streaming GET, following redirects safely. Caller must close."""
        return await self._request("GET", url, headers=headers, identity=accept_encoding_identity)

    async def _request(
        self,
        method: str,
        url: str | ValidatedURL,
        *,
        headers: Mapping[str, str] | None,
        identity: bool,
    ) -> SafeResponse:
        target = (
            url if isinstance(url, ValidatedURL) else await validate_and_resolve(url, self.settings)
        )
        redirects = 0
        seen: set[str] = set()
        while True:
            if target.url in seen:
                raise AppError(ErrorCode.TOO_MANY_REDIRECTS, "The source redirects in a loop.")
            seen.add(target.url)
            response = await self._send_pinned(method, target, headers=headers, identity=identity)
            if response.status_code in _REDIRECT_CODES:
                location = response.headers.get("location")
                await response.aclose()
                if not location:
                    raise AppError(
                        ErrorCode.SOURCE_UNREACHABLE,
                        "The source returned a redirect without a location.",
                    )
                redirects += 1
                if redirects > self.settings.max_redirects:
                    raise AppError(
                        ErrorCode.TOO_MANY_REDIRECTS, "The source redirected too many times."
                    )
                next_url = urljoin(target.url, location)
                target = await validate_and_resolve(next_url, self.settings)
                continue
            return SafeResponse(
                status_code=response.status_code,
                headers=response.headers,
                final_url=target,
                redirects=redirects,
                _response=response,
                _max_bytes=self.max_bytes,
            )

    async def _send_pinned(
        self,
        method: str,
        target: ValidatedURL,
        *,
        headers: Mapping[str, str] | None,
        identity: bool,
    ) -> httpx.Response:
        ip = target.primary_ip
        pinned_host = f"[{ip}]" if ":" in ip else ip
        parts = urlsplit(target.url)
        default_port = _default_port(parts.scheme)
        netloc = pinned_host if target.port == default_port else f"{pinned_host}:{target.port}"
        pinned_url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, ""))

        display_host = f"[{target.host}]" if ":" in target.host else target.host
        host_header = (
            display_host if target.port == default_port else f"{display_host}:{target.port}"
        )
        req_headers: dict[str, str] = {"Host": host_header}
        if identity:
            req_headers["Accept-Encoding"] = "identity"
        if headers:
            req_headers.update(headers)
        extensions: dict[str, Any] = {}
        if parts.scheme == "https" and not target.is_ip_literal:
            extensions["sni_hostname"] = target.host

        request = self._client.build_request(
            method, pinned_url, headers=req_headers, extensions=extensions
        )
        try:
            return await self._client.send(request, stream=True)
        except httpx.ConnectTimeout as exc:
            raise AppError(ErrorCode.SOURCE_TIMEOUT, "Connecting to the source timed out.") from exc
        except httpx.ReadTimeout as exc:
            raise AppError(
                ErrorCode.SOURCE_TIMEOUT, "The source took too long to respond."
            ) from exc
        except httpx.ConnectError as exc:
            raise AppError(
                ErrorCode.SOURCE_UNREACHABLE, "Could not connect to the source."
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                ErrorCode.SOURCE_UNREACHABLE, "The request to the source failed."
            ) from exc


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def raise_for_status(response: SafeResponse) -> None:
    """Translate non-2xx status codes into typed errors."""
    code = response.status_code
    if 200 <= code < 300:
        return
    if code == 404:
        raise AppError(ErrorCode.SOURCE_NOT_FOUND, "The source returned 404 Not Found.")
    if code in (401, 402, 403, 407, 451):
        raise AppError(
            ErrorCode.SOURCE_FORBIDDEN,
            f"The source refused access (HTTP {code}). It may require a login or block automated requests.",
        )
    if code == 429:
        raise AppError(
            ErrorCode.SOURCE_UNREACHABLE,
            "The source is rate limiting requests. Try again later.",
            retryable=True,
        )
    if code >= 500:
        raise AppError(
            ErrorCode.SOURCE_UNREACHABLE,
            f"The source returned a server error (HTTP {code}).",
            retryable=True,
        )
    raise AppError(
        ErrorCode.SOURCE_UNREACHABLE, f"The source returned an unexpected response (HTTP {code})."
    )


@contextlib.asynccontextmanager
async def open_client(
    settings: Settings | None = None, **kwargs: Any
) -> AsyncIterator[SafeHttpClient]:
    client = SafeHttpClient(settings, **kwargs)
    try:
        yield client
    finally:
        await client.aclose()
