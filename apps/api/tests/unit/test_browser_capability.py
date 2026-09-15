"""Browser capability detection must work from inside the API's event loop."""

from __future__ import annotations

import asyncio
import sys
import types
from pathlib import Path

import pytest

from anything_download.tools import registry


def _fake_playwright(monkeypatch: pytest.MonkeyPatch, executable: Path) -> None:
    """Stand-in that behaves like Playwright's sync API: it refuses to start
    inside a running asyncio loop, exactly as the real one does."""

    class _Session:
        chromium = types.SimpleNamespace(executable_path=str(executable))

        def __enter__(self) -> _Session:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return self
            raise RuntimeError(
                "It looks like you are using Playwright Sync API inside the asyncio loop."
            )

        def __exit__(self, *exc: object) -> None:
            return None

    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = _Session  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api)


def test_chromium_detected_from_inside_a_running_event_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    chrome = tmp_path / "chrome"
    chrome.write_bytes(b"")
    _fake_playwright(monkeypatch, chrome)

    async def from_handler() -> bool:
        return registry._chromium_present()

    assert asyncio.run(from_handler()) is True


def test_missing_chromium_executable_is_reported_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_playwright(monkeypatch, tmp_path / "not-installed" / "chrome")

    async def from_handler() -> bool:
        return registry._chromium_present()

    assert registry._chromium_present() is False
    assert asyncio.run(from_handler()) is False


def test_browser_requirement_needs_flag_package_and_executable(
    monkeypatch: pytest.MonkeyPatch, settings
) -> None:
    monkeypatch.setattr(registry, "_chromium_present", lambda: True)
    monkeypatch.setattr(registry, "_importable", lambda name: True)
    assert (
        registry.Runtime(settings.model_copy(update={"enable_browser_tools": False})).has("browser")
        is False
    )
    assert (
        registry.Runtime(settings.model_copy(update={"enable_browser_tools": True})).has("browser")
        is True
    )

    monkeypatch.setattr(registry, "_chromium_present", lambda: False)
    assert (
        registry.Runtime(settings.model_copy(update={"enable_browser_tools": True})).has("browser")
        is False
    )
