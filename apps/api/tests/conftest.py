"""Shared fixtures.

* ``settings``: isolated Settings with a temp storage dir
* ``redis``: fakeredis (async)
* ``store``: JobStore on fakeredis
* ``fake_web``: deterministic fake internet: maps URLs to responses, works with the
                  IP-pinning SafeHttpClient by resolving every host to a public IP and
                  routing on the ``Host`` header.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import fakeredis.aioredis
import httpx
import pytest
import respx

from anything_download import config
from anything_download.api.app import create_app
from anything_download.config import Settings
from anything_download.jobs.store import JobStore
from anything_download.security import urls as urls_mod
from anything_download.storage.local import LocalStorage
from anything_download.tools import registry as tool_registry

PUBLIC_IP = "93.184.216.34"
FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("AD_ENV", "test")
    monkeypatch.setenv("AD_STORAGE_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("AD_LOG_FORMAT", "console")
    monkeypatch.setenv("AD_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("AD_RESULT_TTL_MINUTES", "30")
    monkeypatch.setenv("AD_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("AD_MAX_FILE_SIZE_MB", "50")
    monkeypatch.setenv("AD_MAX_UPLOAD_SIZE_MB", "5")
    monkeypatch.setenv("AD_ENABLE_BROWSER_TOOLS", "false")
    monkeypatch.delenv("AD_ALLOW_PRIVATE_TARGETS", raising=False)
    config.reset_settings_cache()
    tool_registry.reset_runtime()
    yield
    config.reset_settings_cache()
    tool_registry.reset_runtime()


@pytest.fixture
def settings() -> Settings:
    return config.get_settings()


@pytest.fixture
def storage(settings: Settings) -> LocalStorage:
    s = LocalStorage(settings=settings)
    s.ensure_dirs()
    return s


@pytest.fixture
async def redis() -> AsyncIterator[fakeredis.aioredis.FakeRedis]:
    client = fakeredis.aioredis.FakeRedis()
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def store(redis: fakeredis.aioredis.FakeRedis, settings: Settings) -> JobStore:
    return JobStore(redis, settings)


@pytest.fixture
async def api_client(
    settings: Settings, redis: fakeredis.aioredis.FakeRedis
) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client that runs the FastAPI lifespan (sets app.state.ad)."""
    from anything_download.tools.registry import load_all

    load_all()
    app = create_app(settings, redis_client=redis)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def public_dns(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    """Make every hostname resolve to a public IP (tests never touch real DNS)."""
    overrides: dict[str, str] = {}

    async def fake_resolve(host: str, port: int, *, timeout: float = 5.0) -> tuple[str, ...]:
        if urls_mod._is_ip_literal(host):
            return (host,)
        return (overrides.get(host, PUBLIC_IP),)

    monkeypatch.setattr(urls_mod, "resolve_host", fake_resolve)
    # Modules that imported the symbol directly
    import anything_download.media.browser as browser_mod

    monkeypatch.setattr(browser_mod, "resolve_host", fake_resolve)

    def set_ip(host: str, ip: str) -> None:
        overrides[host] = ip

    return set_ip  # type: ignore[return-value]


@dataclass
class FakeResponse:
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    stream: Callable[[], Iterator[bytes]] | None = None


@dataclass
class FakeWeb:
    routes: dict[tuple[str, str], FakeResponse] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)

    def add(
        self,
        url: str,
        body: bytes | str = b"",
        *,
        status: int = 200,
        content_type: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        parts = urlsplit(url)
        key = (parts.hostname or "", parts.path or "/")
        data = body.encode() if isinstance(body, str) else body
        hdrs = dict(headers or {})
        if content_type:
            hdrs.setdefault("content-type", content_type)
        if "content-length" not in {k.lower() for k in hdrs} and "transfer-encoding" not in {
            k.lower() for k in hdrs
        }:
            hdrs["content-length"] = str(len(data))
        self.routes[key] = FakeResponse(status=status, headers=hdrs, body=data)

    def redirect(self, url: str, location: str, status: int = 302) -> None:
        parts = urlsplit(url)
        self.routes[(parts.hostname or "", parts.path or "/")] = FakeResponse(
            status=status, headers={"location": location, "content-length": "0"}
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        host = request.headers.get("host", "").split(":")[0]
        key = (host, request.url.path)
        route = self.routes.get(key)
        if route is None:
            return httpx.Response(404, content=b"not found", headers={"content-type": "text/plain"})
        return httpx.Response(route.status, headers=route.headers, content=route.body)


@pytest.fixture
def fake_web(public_dns: Callable[[str], None]) -> Iterator[FakeWeb]:
    web = FakeWeb()
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as mock:
        mock.route().mock(side_effect=web.handler)
        yield web


def has_ffmpeg() -> bool:
    import shutil

    return bool(shutil.which(os.environ.get("AD_FFMPEG_BIN", "ffmpeg"))) and bool(
        shutil.which(os.environ.get("AD_FFPROBE_BIN", "ffprobe"))
    )


requires_ffmpeg = pytest.mark.skipif(not has_ffmpeg(), reason="ffmpeg/ffprobe not installed")
