"""Direct file resources (a URL that points straight at a file)."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from anything_download.config import Settings
from anything_download.detection.mime import (
    extension_for_mime,
    mime_for_extension,
    normalize_mime,
    resource_type_for_mime,
    sniff,
)
from anything_download.domain import ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.net.client import SafeHttpClient, SafeResponse, raise_for_status
from anything_download.security.filenames import sanitize_extension, sanitize_filename
from anything_download.security.urls import ValidatedURL
from anything_download.tools.base import LocalInput

SNIFF_BYTES = 8192

_CD_FILENAME_STAR = re.compile(r"filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)", re.IGNORECASE)
_CD_FILENAME = re.compile(r'filename\s*=\s*"?([^";]+)"?', re.IGNORECASE)


@dataclass
class DirectDescription:
    mime_type: str | None
    resource_type: ResourceType
    filename: str
    size_bytes: int | None
    declared_mime: str | None
    sniffed_mime: str | None
    warnings: list[str]


def filename_from_disposition(header: str | None) -> str | None:
    if not header:
        return None
    m = _CD_FILENAME_STAR.search(header)
    if m:
        return unquote(m.group(1).strip())
    m = _CD_FILENAME.search(header)
    if m:
        return m.group(1).strip()
    return None


def describe(url: ValidatedURL, response: SafeResponse, head: bytes) -> DirectDescription:
    """Combine headers, URL extension and magic bytes into a trustworthy description."""
    warnings: list[str] = []
    declared = normalize_mime(response.content_type)
    if declared in {
        "application/octet-stream",
        "binary/octet-stream",
        "application/x-download",
        "application/force-download",
    }:
        declared = None
    sniffed = sniff(head)
    sniffed_mime = sniffed[0] if sniffed else None

    hint = filename_from_disposition(response.content_disposition) or url.filename_hint or ""
    hint_ext = sanitize_extension(hint.rsplit(".", 1)[-1]) if "." in hint else ""
    ext_mime = mime_for_extension(hint_ext)

    mime = sniffed_mime or declared or ext_mime
    # Prefer bytes over the header; only warn when the *category* disagrees.
    if (
        sniffed_mime
        and declared
        and resource_type_for_mime(sniffed_mime) != resource_type_for_mime(declared)
    ):
        warnings.append("content_type_mismatch")
    if (
        sniffed_mime
        and ext_mime
        and resource_type_for_mime(sniffed_mime) != resource_type_for_mime(ext_mime)
    ):
        warnings.append("extension_mismatch")

    resource_type = resource_type_for_mime(mime)
    ext = extension_for_mime(mime) or hint_ext or ""
    base = hint.rsplit(".", 1)[0] if "." in hint else hint
    filename = sanitize_filename(base or url.host, fallback="download", ext=ext or None)
    return DirectDescription(
        mime_type=mime,
        resource_type=resource_type,
        filename=filename,
        size_bytes=response.content_length,
        declared_mime=declared,
        sniffed_mime=sniffed_mime,
        warnings=warnings,
    )


ProgressBytes = Callable[[int, int | None], Awaitable[None]]


async def download_to_file(
    http: SafeHttpClient,
    url: ValidatedURL,
    dest_dir: Path,
    *,
    settings: Settings,
    max_bytes: int,
    on_progress: ProgressBytes | None = None,
    is_cancelled: Callable[[], Awaitable[bool]] | None = None,
    filename: str | None = None,
) -> LocalInput:
    """Stream a remote file to disk with size limits, returning a :class:`LocalInput`."""
    response = await http.get(url)
    try:
        raise_for_status(response)
        if response.content_length is not None and response.content_length > max_bytes:
            raise AppError(
                ErrorCode.SOURCE_TOO_LARGE,
                f"The file is {response.content_length // (1024 * 1024)} MB which exceeds the "
                f"{max_bytes // (1024 * 1024)} MB limit.",
            )
        head = await response.read_limited(SNIFF_BYTES)
        desc = describe(response.final_url, response, head)
        if desc.resource_type == ResourceType.WEBPAGE:
            raise AppError(
                ErrorCode.SOURCE_INVALID_CONTENT,
                "The URL returned a webpage instead of a file.",
            )
        name = (
            sanitize_filename(filename, ext=Path(desc.filename).suffix)
            if filename
            else desc.filename
        )
        dest = dest_dir / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        total = response.content_length
        written = 0
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            with tmp.open("wb") as fh:
                # aiter_bytes re-emits the sniffed head, then continues with the body.
                async for chunk in response.aiter_bytes():
                    fh.write(chunk)
                    written += len(chunk)
                    if written > max_bytes:
                        raise AppError(
                            ErrorCode.SOURCE_TOO_LARGE,
                            f"The file exceeds the {max_bytes // (1024 * 1024)} MB limit.",
                        )
                    if on_progress:
                        await on_progress(written, total)
                    if is_cancelled and await is_cancelled():
                        from anything_download.tools.base import JobCancelled

                        raise JobCancelled()
            tmp.replace(dest)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return LocalInput(
            path=dest,
            filename=name,
            mime_type=desc.mime_type or "application/octet-stream",
            resource_type=desc.resource_type,
            size_bytes=written,
        )
    finally:
        await response.aclose()
