"""Tools catalogue, health, readiness and metrics endpoints."""

from __future__ import annotations

import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from anything_download.api.state import AppState, get_state
from anything_download.errors import AppError, ErrorCode, ErrorResponse
from anything_download.jobs.limits import MAX_FILES_PER_JOB, MAX_TEXT_CHARS
from anything_download.tools.registry import ToolView, all_tools, get_tool, tool_view

router = APIRouter()


class ToolsResponse(BaseModel):
    tools: list[ToolView]


@router.get("/tools", response_model=ToolsResponse, tags=["tools"], summary="List available tools")
async def list_tools() -> ToolsResponse:
    return ToolsResponse(tools=[tool_view(t) for t in all_tools()])


class LimitsResponse(BaseModel):
    """Limits a client can check before sending work. The API still enforces every one."""

    max_upload_bytes: int = Field(description="Largest single upload accepted.")
    max_file_bytes: int = Field(description="Largest remote file or result the service handles.")
    max_url_length: int
    max_text_chars: int = Field(description="Largest text input (e.g. QR generator).")
    max_files_per_job: int
    result_ttl_seconds: int = Field(description="How long results are kept before deletion.")
    upload_ttl_seconds: int


@router.get(
    "/limits",
    response_model=LimitsResponse,
    tags=["tools"],
    summary="Public processing limits",
)
async def limits(
    response: Response, state: Annotated[AppState, Depends(get_state)]
) -> LimitsResponse:
    settings = state.settings
    response.headers["Cache-Control"] = "public, max-age=300"
    return LimitsResponse(
        max_upload_bytes=settings.max_upload_size_bytes,
        max_file_bytes=settings.max_file_size_bytes,
        max_url_length=settings.max_url_length,
        max_text_chars=MAX_TEXT_CHARS,
        max_files_per_job=MAX_FILES_PER_JOB,
        result_ttl_seconds=settings.result_ttl_seconds,
        upload_ttl_seconds=settings.upload_ttl_seconds,
    )


@router.get(
    "/tools/{tool_id}",
    response_model=ToolView,
    tags=["tools"],
    summary="Describe a tool",
    responses={404: {"model": ErrorResponse}},
)
async def describe_tool(tool_id: str) -> ToolView:
    return tool_view(get_tool(tool_id))


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, bool]


@router.get("/health", response_model=HealthResponse, tags=["operations"], summary="Liveness probe")
async def health() -> HealthResponse:
    from anything_download import __version__

    return HealthResponse(version=__version__)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    tags=["operations"],
    summary="Readiness probe",
    responses={503: {"model": ReadinessResponse}},
)
async def ready(
    response: Response, state: Annotated[AppState, Depends(get_state)]
) -> ReadinessResponse:
    checks = {
        "redis": await state.store.ping(),
        "storage_writable": _storage_writable(state),
        "ffmpeg": bool(shutil.which(state.settings.ffmpeg_bin))
        and bool(shutil.which(state.settings.ffprobe_bin)),
        # Reported, not gating: under disk pressure the API still serves status and
        # downloads, it only refuses new uploads and jobs.
        "storage_space": state.guard.status().ok,
    }
    ok = checks["redis"] and checks["storage_writable"]
    if not ok:
        response.status_code = 503
    return ReadinessResponse(status="ready" if ok else "degraded", checks=checks)


def _storage_writable(state: AppState) -> bool:
    try:
        state.storage.ensure_dirs()
        probe = state.storage.root / ".write-test"
        probe.write_bytes(b"ok")
        probe.unlink(missing_ok=True)
    except OSError:
        return False
    return True


class MetricsResponse(BaseModel):
    metrics: dict[str, float] = Field(description="Operational counters; no per-user data.")


@router.get(
    "/metrics", response_model=MetricsResponse, tags=["operations"], summary="Operational metrics"
)
async def metrics(state: Annotated[AppState, Depends(get_state)]) -> MetricsResponse:
    if not await state.store.ping():
        raise AppError(
            ErrorCode.SERVICE_UNAVAILABLE, "Metrics are unavailable because Redis is unreachable."
        )
    snapshot = await state.store.metrics_snapshot()
    storage = state.guard.status()
    snapshot["storage_free_bytes"] = float(storage.free_bytes)
    snapshot["storage_pressure"] = 0.0 if storage.ok else 1.0
    if storage.used_bytes is not None:
        snapshot["storage_used_bytes"] = float(storage.used_bytes)
    return MetricsResponse(metrics=snapshot)
