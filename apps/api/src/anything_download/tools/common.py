"""Helpers shared by tool implementations."""

from __future__ import annotations

import shutil
import zipfile
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from anything_download.detection.mime import (
    extension_for_mime,
    mime_for_extension,
    resource_type_for_mime,
    sniff,
)
from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.security.filenames import sanitize_filename
from anything_download.tools.base import (
    InputKind,
    LocalInput,
    Tool,
    ToolContext,
    ToolInput,
    ToolOutput,
    ToolSpec,
)


def describe_local_file(
    path: Path, *, filename: str | None = None, declared_mime: str | None = None
) -> LocalInput:
    """Build a :class:`LocalInput` from a file on disk using magic bytes first."""
    with path.open("rb") as fh:
        head = fh.read(8192)
    sniffed = sniff(head)
    ext = path.suffix.lstrip(".").lower()
    mime = (
        (sniffed[0] if sniffed else None)
        or declared_mime
        or mime_for_extension(ext)
        or "application/octet-stream"
    )
    if mime == "application/octet-stream" and ext in {
        "txt",
        "md",
        "csv",
        "json",
        "xml",
        "html",
        "htm",
        "svg",
    }:
        mime = mime_for_extension(ext) or mime
    resource_type = resource_type_for_mime(mime)
    name = filename or path.name
    final_ext = extension_for_mime(mime) or ext or None
    safe_name = sanitize_filename(
        Path(name).stem if final_ext else name, ext=final_ext, fallback="file"
    )
    return LocalInput(
        path=path,
        filename=safe_name,
        mime_type=mime,
        resource_type=resource_type,
        size_bytes=path.stat().st_size,
    )


def stem_of(source: ToolInput | LocalInput, fallback: str = "anything-download") -> str:
    if isinstance(source, LocalInput):
        return Path(source.filename).stem or fallback
    if source.files:
        return Path(source.files[0].filename).stem or fallback
    if source.analysis and source.analysis.title:
        return sanitize_filename(source.analysis.title, fallback=fallback)
    if source.url is not None:
        hint = Path(source.url.filename_hint).stem
        return sanitize_filename(hint or source.url.host, fallback=fallback)
    return fallback


def output_name(ctx: ToolContext, stem: str, ext: str) -> tuple[Path, str]:
    name = sanitize_filename(stem, fallback=f"anything-download-{ctx.job_id[:8]}", ext=ext)
    return ctx.output_path(name), name


def unique_names(names: Iterable[str]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for n in names:
        safe = sanitize_filename(n, fallback="file")
        if safe in seen:
            seen[safe] += 1
            p = Path(safe)
            safe = f"{p.stem}-{seen[safe]}{p.suffix}"
        else:
            seen[safe] = 0
        out.append(safe)
    return out


def make_zip(destination: Path, files: list[tuple[Path, str]]) -> None:
    names = unique_names(name for _, name in files)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for (path, _), arcname in zip(files, names, strict=True):
            zf.write(path, arcname=arcname)


def move_to_output(ctx: ToolContext, src: Path, filename: str) -> Path:
    dest = ctx.output_path(filename)
    if src.resolve() == dest.resolve():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    return dest


def require_file_type(local: LocalInput, allowed: set[ResourceType], what: str) -> None:
    if local.resource_type not in allowed:
        raise AppError(
            ErrorCode.FILE_TYPE_UNSUPPORTED,
            f"This tool needs {what}, but the file was detected as {local.resource_type.value.lower()} ({local.mime_type}).",
        )


class DownloadOptions(BaseModel):
    model_config = {"extra": "forbid"}
    format: str = "best"
    """For platform sources: a format id from the analysis. Ignored for direct files."""


class DownloadTool(Tool):
    """Fetch a direct or platform file and hand it to the user unchanged."""

    def __init__(
        self,
        tool_id: str,
        category: str,
        accepts: set[ResourceType],
        *,
        platform: bool,
        order: int,
        requires: set[str] | None = None,
        platform_default_format: str = "best",
    ) -> None:
        self.spec = ToolSpec(
            id=tool_id,
            category=category,  # type: ignore[arg-type]
            capability=Capability.DOWNLOAD,
            inputs=frozenset({InputKind.URL}),
            accepts=frozenset(accepts),
            options_model=DownloadOptions,
            requires=frozenset(requires or set()),
            fetch_input=True,
            output="file",
            accepts_platform_media=platform,
            platform_default_format=platform_default_format,
            order=order,
        )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        local = source.file
        dest = move_to_output(ctx, local.path, local.filename)
        return ToolOutput(
            file_path=dest,
            filename=local.filename,
            mime_type=local.mime_type,
            resource_type=local.resource_type,
        )
