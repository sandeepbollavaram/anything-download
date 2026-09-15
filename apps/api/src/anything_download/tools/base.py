"""Tool abstractions.

A *tool* is a user-facing operation (e.g. ``video-to-mp3``). Tools declare a
:class:`ToolSpec` describing which inputs and resource types they accept and
which runtime dependencies they need. The worker resolves inputs (downloads a
URL or locates an upload), then calls :meth:`Tool.run` with a
:class:`ToolContext`.
"""

from __future__ import annotations

import abc
import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from anything_download.analysis.models import URLAnalysis
from anything_download.config import Settings
from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.jobs.models import JobProgress
from anything_download.net.client import SafeHttpClient
from anything_download.security.urls import ValidatedURL
from anything_download.storage.local import LocalStorage

ToolCategory = Literal["video", "image", "pdf", "audio", "web", "utility"]


class InputKind(StrEnum):
    URL = "url"
    UPLOAD = "upload"
    UPLOADS = "uploads"
    TEXT = "text"


class NoOptions(BaseModel):
    model_config = {"extra": "forbid"}


@dataclass(frozen=True)
class ToolSpec:
    id: str
    category: ToolCategory
    capability: Capability
    inputs: frozenset[InputKind]
    accepts: frozenset[ResourceType]
    """Resource types this tool applies to. Empty means 'not resource based' (e.g. QR generate)."""
    options_model: type[BaseModel] = NoOptions
    requires: frozenset[str] = frozenset()
    """Runtime requirements: 'ffmpeg', 'browser', 'platform_extractors'."""
    fetch_input: bool = True
    """When given a URL, download it to a local file before running."""
    output: Literal["file", "data", "file+data"] = "file"
    accepts_platform_media: bool = False
    """True if the tool can operate on platform (e.g. YouTube) sources via the extractor."""
    platform_default_format: str = "best"
    """Format id fetched from a platform source when the options do not specify one."""
    seo_page: bool = True
    order: int = 100


@dataclass
class LocalInput:
    path: Path
    filename: str
    mime_type: str
    resource_type: ResourceType
    size_bytes: int


@dataclass
class ToolInput:
    kind: InputKind
    url: ValidatedURL | None = None
    files: list[LocalInput] = field(default_factory=list)
    text: str | None = None
    analysis: URLAnalysis | None = None

    @property
    def file(self) -> LocalInput:
        if not self.files:
            raise AppError(ErrorCode.TOOL_INPUT_MISMATCH, "This tool requires a file input.")
        return self.files[0]

    def require_url(self) -> ValidatedURL:
        if self.url is None:
            raise AppError(ErrorCode.TOOL_INPUT_MISMATCH, "This tool requires a URL input.")
        return self.url


@dataclass
class ToolOutput:
    file_path: Path | None = None
    filename: str | None = None
    mime_type: str | None = None
    resource_type: ResourceType = ResourceType.UNKNOWN
    data: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)


class ToolContext:
    """Runtime services handed to a tool while it runs."""

    def __init__(
        self,
        *,
        job_id: str,
        settings: Settings,
        storage: LocalStorage,
        work_dir: Path,
        output_dir: Path,
        http: SafeHttpClient,
        report: Callable[[JobProgress], Awaitable[None]],
        is_cancelled: Callable[[], Awaitable[bool]],
    ) -> None:
        self.job_id = job_id
        self.settings = settings
        self.storage = storage
        self.work_dir = work_dir
        self.output_dir = output_dir
        self.http = http
        self._report = report
        self.is_cancelled = is_cancelled
        self._last_report = 0.0
        self.deadline = time.monotonic() + settings.max_job_duration_seconds

    @property
    def remaining_seconds(self) -> float:
        return max(1.0, self.deadline - time.monotonic())

    async def report(
        self,
        phase: str,
        *,
        percent: float | None = None,
        message: str | None = None,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        if not force and now - self._last_report < 0.75:
            return
        self._last_report = now
        await self._report(JobProgress(phase=phase, percent=percent, message=message))

    async def check_cancelled(self) -> None:
        if await self.is_cancelled():
            raise JobCancelled()

    def output_path(self, filename: str) -> Path:
        return self.storage.resolve_within(self.output_dir, filename)

    def work_path(self, filename: str) -> Path:
        return self.storage.resolve_within(self.work_dir, filename)

    async def run_blocking(self, fn: Callable[..., Any], *args: Any) -> Any:
        """Run CPU-bound work in a thread so the event loop keeps serving heartbeats."""
        return await asyncio.to_thread(fn, *args)


class JobCancelled(Exception):  # noqa: N818 - control-flow signal, not an error
    """Raised inside a tool when the user cancelled the job."""


class Tool(abc.ABC):
    spec: ToolSpec

    @abc.abstractmethod
    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput: ...

    def validate_options(self, raw: dict[str, Any]) -> BaseModel:
        try:
            return self.spec.options_model.model_validate(raw or {})
        except ValueError as exc:  # pydantic.ValidationError subclasses ValueError
            raise AppError(
                ErrorCode.INVALID_OPTIONS,
                "The provided options are not valid for this tool.",
                details={"errors": _pydantic_errors(exc)},
            ) from exc

    def check_input(self, source: ToolInput) -> None:
        """Verify the resolved input matches what the tool accepts."""
        if source.kind not in self.spec.inputs:
            raise AppError(
                ErrorCode.TOOL_INPUT_MISMATCH,
                f"Tool '{self.spec.id}' does not accept '{source.kind.value}' input.",
            )
        if self.spec.accepts and source.files:
            for f in source.files:
                if f.resource_type not in self.spec.accepts:
                    raise AppError(
                        ErrorCode.FILE_TYPE_UNSUPPORTED,
                        f"Tool '{self.spec.id}' cannot process {f.resource_type.value.lower()} files"
                        f" ({f.mime_type}).",
                    )


def _pydantic_errors(exc: Exception) -> list[dict[str, Any]]:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            return [
                {"loc": list(map(str, e.get("loc", []))), "msg": e.get("msg", "")} for e in errors()
            ]
        except Exception:  # noqa: BLE001
            return []
    return [{"loc": [], "msg": str(exc)}]
