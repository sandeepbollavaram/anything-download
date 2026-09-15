"""Headless browser rendering (Playwright + Chromium) for URL→PDF and screenshots.

Only enabled when ``AD_ENABLE_BROWSER_TOOLS=true`` and Playwright with Chromium
is installed in the worker image. Every sub-request the page makes is checked
against the SSRF policy before it is allowed to proceed.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from anything_download.config import Settings
from anything_download.errors import AppError, ErrorCode
from anything_download.logging import get_logger
from anything_download.security.urls import (
    ValidatedURL,
    interpret_ip,
    is_blocked_hostname,
    is_blocked_ip,
    resolve_host,
)

log = get_logger(__name__)

_BLOCKED_RESOURCE_TYPES = {"websocket", "eventsource", "manifest"}


def host_resolver_rules(url: ValidatedURL, settings: Settings) -> str | None:
    """Pin the navigation host to the IP that was already validated.

    ``_HostPolicy`` can only re-resolve a hostname and then hand the request
    back to Chromium, which resolves it again itself, so a DNS answer that
    flips to a private address between those two lookups would be honoured.
    Chromium's own resolver rules close that race for the target host: the
    mapping is applied inside the browser, and unlike rewriting the URL to an
    IP it leaves the hostname (and therefore SNI and certificate validation)
    untouched. Sub-resources on other hosts stay on the per-request policy.
    """
    if settings.allow_private_targets or url.is_ip_literal:
        return None
    ip = url.primary_ip
    mapped = f"[{ip}]" if ":" in ip else ip
    return f"MAP {url.host} {mapped}"


class _HostPolicy:
    """Decide whether a request host may be contacted.

    Allows are never cached: Chromium would otherwise keep using a hostname
    after DNS flipped to a private address. Denials are cached for the render.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._denied: set[str] = set()

    async def allowed(self, url: str) -> bool:
        try:
            parts = urlsplit(url)
        except ValueError:
            return False
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            return parts.scheme in {"data", "blob", "about"}
        host = parts.hostname.lower()
        if host in self._denied:
            return False
        ok = await self._evaluate(host, parts.port)
        if not ok:
            self._denied.add(host)
        return ok

    async def _evaluate(self, host: str, port: int | None) -> bool:
        if self.settings.allow_private_targets:
            return True
        if is_blocked_hostname(host):
            return False
        parsed_ip = interpret_ip(host)
        if parsed_ip is not None:
            return not is_blocked_ip(parsed_ip)
        try:
            ips = await resolve_host(host, port or 443, timeout=3.0)
        except AppError:
            return False
        return not any(is_blocked_ip(ip) for ip in ips)


@contextlib.asynccontextmanager
async def _page(
    url: ValidatedURL, settings: Settings, *, viewport: dict[str, int], timeout: float
) -> AsyncIterator[Any]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - guarded by runtime check
        raise AppError(
            ErrorCode.TOOL_UNAVAILABLE, "Browser rendering is not installed on this server."
        ) from exc

    policy = _HostPolicy(settings)
    launch_args = [
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-first-run",
        "--disable-extensions",
        "--disable-background-networking",
    ]
    rules = host_resolver_rules(url, settings)
    if rules:
        launch_args.append(f"--host-resolver-rules={rules}")
    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(headless=True, args=launch_args)
        except Exception as exc:
            log.error("browser.launch_failed", error=str(exc)[:300])
            raise AppError(
                ErrorCode.TOOL_UNAVAILABLE, "The browser could not be started on this server."
            ) from exc
        try:
            context = await browser.new_context(
                viewport=viewport,  # type: ignore[arg-type]
                user_agent=settings.user_agent,
                java_script_enabled=True,
                accept_downloads=False,
                ignore_https_errors=False,
                service_workers="block",
            )
            context.set_default_timeout(timeout * 1000)

            async def route_handler(route: Any, request: Any) -> None:
                if request.resource_type in _BLOCKED_RESOURCE_TYPES or not await policy.allowed(
                    request.url
                ):
                    await route.abort("blockedbyclient")
                    return
                await route.continue_()

            await context.route("**/*", route_handler)
            page = await context.new_page()
            try:
                response = await page.goto(url.url, wait_until="load", timeout=timeout * 1000)
            except Exception as exc:
                message = str(exc)
                if "Timeout" in message:
                    raise AppError(
                        ErrorCode.SOURCE_TIMEOUT, "The page took too long to load."
                    ) from exc
                raise AppError(
                    ErrorCode.SOURCE_UNREACHABLE, "The page could not be loaded."
                ) from exc
            if response is not None and response.status >= 400:
                raise AppError(
                    ErrorCode.SOURCE_UNREACHABLE, f"The page returned HTTP {response.status}."
                )
            with contextlib.suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=min(5000, timeout * 1000 / 3))
            yield page
        finally:
            with contextlib.suppress(Exception):
                await browser.close()


async def render_pdf(
    url: ValidatedURL,
    dest: Path,
    *,
    settings: Settings,
    page_size: str,
    landscape: bool,
    print_background: bool,
    timeout: float,
) -> None:
    async with _page(
        url, settings, viewport={"width": 1280, "height": 900}, timeout=timeout
    ) as page:
        try:
            await page.emulate_media(media="print")
            await asyncio.wait_for(
                page.pdf(
                    path=str(dest),
                    format=page_size,
                    landscape=landscape,
                    print_background=print_background,
                    margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"},
                ),
                timeout=timeout,
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                ErrorCode.PROCESSING_FAILED, "The page could not be rendered to PDF."
            ) from exc
    _enforce_output_size(dest, settings)


async def screenshot(
    url: ValidatedURL,
    dest: Path,
    *,
    settings: Settings,
    width: int,
    height: int,
    full_page: bool,
    timeout: float,
) -> None:
    async with _page(
        url, settings, viewport={"width": width, "height": height}, timeout=timeout
    ) as page:
        try:
            await asyncio.wait_for(
                page.screenshot(path=str(dest), full_page=full_page, type="png"), timeout=timeout
            )
        except AppError:
            raise
        except Exception as exc:
            raise AppError(ErrorCode.PROCESSING_FAILED, "The page could not be captured.") from exc
    _enforce_output_size(dest, settings)


def _enforce_output_size(dest: Path, settings: Settings) -> None:
    try:
        size = dest.stat().st_size
    except OSError as exc:
        raise AppError(ErrorCode.PROCESSING_FAILED, "The browser produced no output file.") from exc
    if size > settings.max_file_size_bytes:
        dest.unlink(missing_ok=True)
        raise AppError(
            ErrorCode.FILE_TOO_LARGE,
            f"The rendered file exceeded the {settings.max_file_size_mb} MB limit.",
        )
