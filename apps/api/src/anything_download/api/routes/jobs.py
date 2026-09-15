"""Job endpoints: create, inspect, cancel, fetch result, delete."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse

from anything_download.api.state import AppState, get_state
from anything_download.domain import JobStatus
from anything_download.errors import AppError, ErrorCode, ErrorResponse
from anything_download.jobs.limits import MAX_TEXT_CHARS
from anything_download.jobs.models import JobCreateRequest, JobRecord, JobView, UploadRecord
from anything_download.logging import get_logger
from anything_download.security.filenames import content_disposition
from anything_download.storage.local import new_id, validate_id
from anything_download.tools.base import Tool
from anything_download.tools.registry import get_tool, runtime

log = get_logger(__name__)
router = APIRouter(tags=["jobs"])

_ERR: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    410: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


def _job_id(value: str) -> str:
    try:
        return validate_id(value)
    except ValueError as exc:
        raise AppError(ErrorCode.JOB_NOT_FOUND, "This job does not exist or has expired.") from exc


@router.post(
    "/jobs",
    response_model=JobView,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a processing job",
    description="Queues a tool run. Poll `GET /jobs/{id}` until `status` is terminal.",
    responses={
        404: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def create_job(
    body: JobCreateRequest, state: Annotated[AppState, Depends(get_state)]
) -> JobView:
    tool = get_tool(body.tool)
    if not runtime().available(tool.spec):
        raise AppError(
            ErrorCode.TOOL_UNAVAILABLE,
            "This tool is not available on this server.",
            details={"missing": runtime().missing(tool.spec)},
        )
    if body.input.kind not in {k.value for k in tool.spec.inputs}:
        raise AppError(
            ErrorCode.TOOL_INPUT_MISMATCH,
            f"Tool '{tool.spec.id}' does not accept '{body.input.kind}' input.",
        )
    tool.validate_options(body.options)
    if body.input.kind == "url" and body.input.url is not None:
        from anything_download.security.urls import parse_url

        body.input.url = parse_url(body.input.url, state.settings).url
    # Reject a file the tool cannot process now, with the same error the worker
    # would raise, instead of queueing a job that is certain to fail.
    if body.input.kind == "upload" and body.input.upload_id is not None:
        _require_accepted(tool, await _require_upload(state, body.input.upload_id))
    if body.input.kind == "uploads" and body.input.upload_ids:
        for uid in body.input.upload_ids:
            _require_accepted(tool, await _require_upload(state, uid))
    if (
        body.input.kind == "text"
        and body.input.text is not None
        and len(body.input.text) > MAX_TEXT_CHARS
    ):
        raise AppError(
            ErrorCode.INVALID_OPTIONS, f"Text input is limited to {MAX_TEXT_CHARS:,} characters."
        )
    state.guard.require()

    record = JobRecord(id=new_id(), tool=tool.spec.id, input=body.input, options=body.options)
    await state.store.create(record)
    log.info("job.created", job_id=record.id, tool=record.tool, input_kind=body.input.kind)
    return record.public()


async def _require_upload(state: AppState, upload_id: str) -> UploadRecord:
    try:
        validate_id(upload_id)
    except ValueError as exc:
        raise AppError(
            ErrorCode.UPLOAD_NOT_FOUND, "The uploaded file reference is invalid."
        ) from exc
    upload = await state.store.get_upload(upload_id)
    if upload is None:
        raise AppError(
            ErrorCode.UPLOAD_NOT_FOUND, "The uploaded file has expired or does not exist."
        )
    return upload


def _require_accepted(tool: Tool, upload: UploadRecord) -> None:
    """Mirror of ``Tool.check_input`` for uploads, which is otherwise only run in the worker."""
    if tool.spec.accepts and upload.resource_type not in tool.spec.accepts:
        raise AppError(
            ErrorCode.FILE_TYPE_UNSUPPORTED,
            f"Tool '{tool.spec.id}' cannot process {upload.resource_type.value.lower()} files"
            f" ({upload.mime_type}).",
        )


@router.get("/jobs/{job_id}", response_model=JobView, summary="Get job status", responses=_ERR)
async def get_job(job_id: str, state: Annotated[AppState, Depends(get_state)]) -> JobView:
    record = await state.store.require(_job_id(job_id))
    return record.public()


@router.post(
    "/jobs/{job_id}/cancel", response_model=JobView, summary="Cancel a job", responses=_ERR
)
async def cancel_job(job_id: str, state: Annotated[AppState, Depends(get_state)]) -> JobView:
    record = await state.store.request_cancel(_job_id(job_id))
    return record.public()


@router.get(
    "/jobs/{job_id}/result",
    summary="Download the job result file",
    response_class=FileResponse,
    responses={
        200: {"content": {"application/octet-stream": {}}, "description": "The produced file."},
        **_ERR,
    },
)
async def get_result(job_id: str, state: Annotated[AppState, Depends(get_state)]) -> Response:
    jid = _job_id(job_id)
    record = await state.store.require(jid)
    if record.status == JobStatus.EXPIRED:
        raise AppError(ErrorCode.JOB_EXPIRED, "This result has expired and was deleted.")
    if record.status == JobStatus.CANCELLED:
        raise AppError(ErrorCode.JOB_CANCELLED, "This job was cancelled.")
    if record.status != JobStatus.COMPLETED:
        raise AppError(ErrorCode.JOB_NOT_READY, "This job has not finished yet.")
    if record.result is None or record.result.file is None:
        raise AppError(ErrorCode.JOB_NOT_READY, "This job produced no downloadable file.")
    try:
        path = state.storage.resolve_within(state.storage.job_dir(jid), record.result.file.filename)
    except ValueError as exc:
        raise AppError(ErrorCode.JOB_NOT_FOUND, "The result file could not be located.") from exc
    if not path.is_file():
        await state.store.mark_expired(jid)
        raise AppError(ErrorCode.JOB_EXPIRED, "This result has expired and was deleted.")
    mime = record.result.file.mime_type
    headers = {
        "Content-Disposition": content_disposition(
            record.result.file.filename, inline=_serve_inline(mime)
        ),
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    }
    # Chrome will not render a PDF whose response carries a CSP sandbox, which would
    # break the result page's <iframe> preview; its viewer isolates PDF scripts itself.
    if mime != "application/pdf":
        headers["Content-Security-Policy"] = _RESULT_CSP
    return FileResponse(path, media_type=mime, headers=headers)


# Results are served from the site's own origin in production (/api is routed there),
# so anything a browser would execute as a document must neither render inline nor
# run script if opened directly. <img>/<video>/<audio> embeds ignore both headers.
_RESULT_CSP = (
    "default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'; sandbox"
)
_INLINE_TYPES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "image/webp",
        "image/avif",
        "image/bmp",
        "application/pdf",
        "text/plain",
    }
)


def _serve_inline(mime: str) -> bool:
    """Inline only for types that cannot carry script. SVG in particular is served as an attachment."""
    return mime in _INLINE_TYPES or mime.startswith(("audio/", "video/"))


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job and its files now",
    responses={404: {"model": ErrorResponse}},
)
async def delete_job(job_id: str, state: Annotated[AppState, Depends(get_state)]) -> Response:
    jid = _job_id(job_id)
    record = await state.store.require(jid)
    if not record.status.is_terminal:
        await state.store.request_cancel(jid)
    await state.storage.delete_job(jid)
    await state.store.delete(jid)
    log.info("job.deleted", job_id=jid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
