"""Upload endpoint.

Files are streamed straight to disk (never buffered in memory), size-limited
while streaming, sniffed for their real type, and expire after
``AD_UPLOAD_TTL_MINUTES``.

The request body is the raw file; the original name is passed in the
``X-File-Name`` header (percent-encoded UTF-8). This keeps uploads streamable
and lets browsers report real progress via XHR.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, Request, Response, status

from anything_download.api.state import AppState, get_state
from anything_download.detection.mime import (
    extension_for_mime,
    mime_for_extension,
    normalize_mime,
    resource_type_for_mime,
    sniff,
)
from anything_download.domain import ResourceType
from anything_download.errors import AppError, ErrorCode, ErrorResponse
from anything_download.jobs.models import UploadRecord, UploadView
from anything_download.jobs.store import upload_expiry
from anything_download.logging import get_logger
from anything_download.security.filenames import sanitize_filename
from anything_download.storage.local import new_id, validate_id
from anything_download.tools.base import InputKind
from anything_download.tools.registry import tools_for

_SPACE_CHECK_BYTES = 8 * 1024 * 1024

log = get_logger(__name__)
router = APIRouter(tags=["uploads"])

_ACCEPTED_TYPES = {ResourceType.VIDEO, ResourceType.IMAGE, ResourceType.AUDIO, ResourceType.PDF}


def _view(record: UploadRecord) -> UploadView:
    single = tools_for(record.resource_type, InputKind.UPLOAD)
    seen = {t.spec.id for t in single}
    tools = single + [
        t for t in tools_for(record.resource_type, InputKind.UPLOADS) if t.spec.id not in seen
    ]
    return UploadView(
        id=record.id,
        filename=record.filename,
        mime_type=record.mime_type,
        size_bytes=record.size_bytes,
        resource_type=record.resource_type,
        expires_at=record.expires_at,
        tools=[t.spec.id for t in tools],
    )


@router.post(
    "/uploads",
    response_model=UploadView,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a file for processing",
    description="Send the raw file bytes as the request body with an `X-File-Name` header.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
    responses={
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
    },
)
async def upload(
    request: Request,
    state: Annotated[AppState, Depends(get_state)],
    x_file_name: Annotated[str | None, Header()] = None,
    content_length: Annotated[int | None, Header()] = None,
) -> UploadView:
    settings = state.settings
    limit = settings.max_upload_size_bytes
    if content_length is not None and content_length > limit:
        raise AppError(
            ErrorCode.FILE_TOO_LARGE, f"Uploads are limited to {settings.max_upload_size_mb} MB."
        )
    # Global disk pressure: refuse before reading a byte. Without a Content-Length the
    # stream is re-checked as it arrives (below).
    state.guard.require(content_length or 0)

    original_name = unquote(x_file_name)[:255] if x_file_name else "upload"
    upload_id = new_id()
    upload_dir = state.storage.create_upload_dir(upload_id)
    path = upload_dir / "file"

    head = bytearray()

    async def chunks() -> AsyncIterator[bytes]:
        since_check = 0
        async for chunk in request.stream():
            if len(head) < 8192:
                head.extend(chunk[: 8192 - len(head)])
            since_check += len(chunk)
            if since_check >= _SPACE_CHECK_BYTES:
                since_check = 0
                state.guard.require_free_space()
            yield chunk

    try:
        size = await state.storage.write_stream(path, chunks(), max_bytes=limit)
    except ValueError as exc:
        await state.storage.delete_upload(upload_id)
        raise AppError(
            ErrorCode.FILE_TOO_LARGE, f"Uploads are limited to {settings.max_upload_size_mb} MB."
        ) from exc
    except Exception:
        await state.storage.delete_upload(upload_id)
        raise

    if size == 0:
        await state.storage.delete_upload(upload_id)
        raise AppError(ErrorCode.VALIDATION_ERROR, "The uploaded file is empty.")

    sniffed = sniff(bytes(head))
    ext_hint = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    declared = normalize_mime(request.headers.get("x-file-type"))
    if declared in {"application/octet-stream", None}:
        declared = None
    mime = (sniffed[0] if sniffed else None) or declared or mime_for_extension(ext_hint)
    resource_type = resource_type_for_mime(mime)
    if resource_type not in _ACCEPTED_TYPES:
        await state.storage.delete_upload(upload_id)
        raise AppError(
            ErrorCode.FILE_TYPE_UNSUPPORTED,
            "Only video, audio, image and PDF files can be uploaded."
            + (f" Detected: {mime}." if mime else " The file type could not be recognized."),
        )
    assert mime is not None
    final_ext = extension_for_mime(mime) or ext_hint or None
    stem = original_name.rsplit(".", 1)[0] if "." in original_name else original_name
    filename = sanitize_filename(stem, fallback="upload", ext=final_ext)

    record = UploadRecord(
        id=upload_id,
        filename=filename,
        mime_type=mime,
        size_bytes=size,
        resource_type=resource_type,
        expires_at=upload_expiry(settings),
    )
    await state.store.save_upload(record)
    log.info("upload.stored", upload_id=upload_id, resource_type=resource_type.value, size=size)
    return _view(record)


@router.get(
    "/uploads/{upload_id}",
    response_model=UploadView,
    summary="Inspect an upload",
    responses={404: {"model": ErrorResponse}},
)
async def get_upload(upload_id: str, state: Annotated[AppState, Depends(get_state)]) -> UploadView:
    try:
        validate_id(upload_id)
    except ValueError as exc:
        raise AppError(ErrorCode.UPLOAD_NOT_FOUND, "Unknown upload.") from exc
    record = await state.store.get_upload(upload_id)
    if record is None:
        raise AppError(
            ErrorCode.UPLOAD_NOT_FOUND, "The uploaded file has expired or does not exist."
        )
    return _view(record)


@router.delete(
    "/uploads/{upload_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an upload now",
    responses={404: {"model": ErrorResponse}},
)
async def delete_upload(upload_id: str, state: Annotated[AppState, Depends(get_state)]) -> Response:
    try:
        validate_id(upload_id)
    except ValueError as exc:
        raise AppError(ErrorCode.UPLOAD_NOT_FOUND, "Unknown upload.") from exc
    await state.storage.delete_upload(upload_id)
    await state.store.delete_upload(upload_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
