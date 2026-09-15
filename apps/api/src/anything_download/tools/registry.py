"""Tool registry and capability resolution."""

from __future__ import annotations

import concurrent.futures
import importlib
import shutil
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from anything_download.config import Settings, get_settings
from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.tools.base import InputKind, Tool, ToolSpec

_TOOLS: dict[str, Tool] = {}
_LOADED = False

_TOOL_MODULES = (
    "anything_download.tools.video",
    "anything_download.tools.image",
    "anything_download.tools.pdf",
    "anything_download.tools.audio",
    "anything_download.tools.web",
    "anything_download.tools.utility",
)


def register(tool: Tool) -> Tool:
    if tool.spec.id in _TOOLS:
        raise RuntimeError(f"duplicate tool id {tool.spec.id}")
    _TOOLS[tool.spec.id] = tool
    return tool


def load_all() -> None:
    global _LOADED  # noqa: PLW0603
    if _LOADED:
        return
    for module in _TOOL_MODULES:
        importlib.import_module(module)
    _LOADED = True


def all_tools() -> list[Tool]:
    load_all()
    return sorted(_TOOLS.values(), key=lambda t: (t.spec.order, t.spec.id))


def get_tool(tool_id: str) -> Tool:
    load_all()
    tool = _TOOLS.get(tool_id)
    if tool is None:
        raise AppError(ErrorCode.TOOL_NOT_FOUND, f"Unknown tool '{tool_id}'.")
    return tool


class Runtime:
    """Which optional runtime requirements are satisfied in this environment."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache: dict[str, bool] = {}

    def has(self, requirement: str) -> bool:
        if requirement in self._cache:
            return self._cache[requirement]
        value: bool
        if requirement == "ffmpeg":
            value = bool(shutil.which(self.settings.ffmpeg_bin)) and bool(
                shutil.which(self.settings.ffprobe_bin)
            )
        elif requirement == "browser":
            value = (
                self.settings.enable_browser_tools
                and _importable("playwright")
                and _chromium_present()
            )
        elif requirement == "platform_extractors":
            value = self.settings.enable_platform_extractors and _importable("yt_dlp")
        else:
            value = False
        self._cache[requirement] = value
        return value

    def available(self, spec: ToolSpec) -> bool:
        return all(self.has(req) for req in spec.requires)

    def missing(self, spec: ToolSpec) -> list[str]:
        return [req for req in spec.requires if not self.has(req)]


def _importable(module: str) -> bool:
    try:
        importlib.import_module(module)
    except Exception:  # noqa: BLE001
        return False
    return True


def _chromium_present() -> bool:
    """True only when Playwright can see a Chromium executable (not just the Python package).

    The probe runs in its own thread. Playwright's sync API refuses to start inside
    a running asyncio loop, and this is first called from async FastAPI handlers,
    so probing inline raised, returned False, and the cached False made browser
    tools permanently unavailable even with Chromium installed.
    """

    def probe() -> bool:
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                return Path(playwright.chromium.executable_path).is_file()
        except Exception:  # noqa: BLE001
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        try:
            return pool.submit(probe).result(timeout=60)
        except Exception:  # noqa: BLE001
            return False


_runtime: Runtime | None = None


def runtime() -> Runtime:
    global _runtime  # noqa: PLW0603
    if _runtime is None:
        _runtime = Runtime()
    return _runtime


def reset_runtime() -> None:
    global _runtime  # noqa: PLW0603
    _runtime = None


def tools_for(
    resource_type: ResourceType,
    input_kind: InputKind,
    *,
    platform_media: bool = False,
    only_available: bool = True,
) -> list[Tool]:
    """Tools applicable to a resource of the given type arriving via ``input_kind``."""
    rt = runtime()
    result: list[Tool] = []
    for tool in all_tools():
        spec = tool.spec
        if input_kind not in spec.inputs:
            continue
        if platform_media:
            if not spec.accepts_platform_media:
                continue
        elif not spec.accepts or resource_type not in spec.accepts:
            continue
        if only_available and not rt.available(spec):
            continue
        result.append(tool)
    return result


def capabilities_for(tools: list[Tool]) -> list[Capability]:
    seen: list[Capability] = []
    for tool in tools:
        if tool.spec.capability not in seen:
            seen.append(tool.spec.capability)
    return seen


class ToolView(BaseModel):
    id: str
    category: str
    capability: Capability
    inputs: list[InputKind]
    accepts: list[ResourceType]
    requires: list[str]
    available: bool
    missing_requirements: list[str] = Field(default_factory=list)
    output: str
    options_schema: dict[str, Any]
    seo_page: bool


def tool_view(tool: Tool) -> ToolView:
    rt = runtime()
    spec = tool.spec
    return ToolView(
        id=spec.id,
        category=spec.category,
        capability=spec.capability,
        inputs=sorted(spec.inputs, key=lambda k: k.value),
        accepts=sorted(spec.accepts, key=lambda r: r.value),
        requires=sorted(spec.requires),
        available=rt.available(spec),
        missing_requirements=rt.missing(spec),
        output=spec.output,
        options_schema=spec.options_model.model_json_schema(),
        seo_page=spec.seo_page,
    )
