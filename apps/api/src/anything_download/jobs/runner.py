"""Executes a single job: resolve inputs, run the tool, publish the result."""

from __future__ import annotations

import asyncio
import contextlib
import time
from pathlib import Path

from anything_download.config import Settings
from anything_download.domain import JobStatus, ResourceType
from anything_download.errors import AppError, ErrorCode, ErrorPayload
from anything_download.extractors.direct import download_to_file
from anything_download.extractors.registry import find_extractor
from anything_download.jobs.limits import MAX_FILES_PER_JOB
from anything_download.jobs.models import JobProgress, JobRecord, JobResult, ResultFile
from anything_download.jobs.store import JobStore, result_expiry
from anything_download.logging import get_logger
from anything_download.net.client import SafeHttpClient
from anything_download.security.urls import parse_url, validate_and_resolve
from anything_download.storage.guard import StorageGuard
from anything_download.storage.local import LocalStorage
from anything_download.tools.base import (
    InputKind,
    JobCancelled,
    LocalInput,
    Tool,
    ToolContext,
    ToolInput,
    ToolOutput,
)
from anything_download.tools.common import describe_local_file
from anything_download.tools.registry import get_tool, runtime

log = get_logger(__name__)


class JobRunner:
    def __init__(self, store: JobStore, storage: LocalStorage, settings: Settings) -> None:
        self.store = store
        self.storage = storage
        self.settings = settings
        self.guard = StorageGuard(settings, storage.root)

    async def run(self, record: JobRecord) -> None:
        job_id = record.id
        started = time.monotonic()
        work_dir = self.storage.create_work_dir(job_id)
        output_dir = self.storage.create_job_dir(job_id)
        http = SafeHttpClient(self.settings)

        async def report(progress: JobProgress) -> None:
            await self.store.set_progress(job_id, progress)

        async def is_cancelled() -> bool:
            return await self.store.is_cancel_requested(job_id)

        ctx = ToolContext(
            job_id=job_id,
            settings=self.settings,
            storage=self.storage,
            work_dir=work_dir,
            output_dir=output_dir,
            http=http,
            report=report,
            is_cancelled=is_cancelled,
        )
        try:
            # A job queued before the disk filled must not start writing now; it fails
            # retryably instead (the API refuses new jobs under the same condition).
            self.guard.require()
            tool = get_tool(record.tool)
            if not runtime().available(tool.spec):
                raise AppError(
                    ErrorCode.TOOL_UNAVAILABLE,
                    "This tool is not available on this server (missing runtime requirement).",
                    details={"missing": runtime().missing(tool.spec)},
                )
            options = tool.validate_options(record.options)
            source = await asyncio.wait_for(
                self._resolve_input(record, tool, ctx, options),
                timeout=self.settings.max_job_duration_seconds,
            )
            tool.check_input(source)
            await ctx.check_cancelled()
            await ctx.report("processing", force=True)
            output: ToolOutput = await asyncio.wait_for(
                tool.run(ctx, source, options), timeout=max(1.0, ctx.remaining_seconds)
            )
            await ctx.check_cancelled()
            await self._publish(record, output)
            await self.store.observe_duration("job_duration", time.monotonic() - started)
            log.info(
                "job.completed",
                job_id=job_id,
                tool=record.tool,
                seconds=round(time.monotonic() - started, 2),
            )
        except JobCancelled:
            await self.store.mark_cancelled(job_id)
            await self.storage.delete_tree(output_dir)
            log.info("job.cancelled", job_id=job_id, tool=record.tool)
        except TimeoutError:
            await self._fail(
                record,
                AppError(
                    ErrorCode.PROCESSING_TIMEOUT,
                    "The job exceeded the maximum processing time and was stopped.",
                ),
            )
        except AppError as exc:
            await self._fail(record, exc)
        except Exception as exc:
            log.exception("job.crashed", job_id=job_id, tool=record.tool, error=type(exc).__name__)
            await self._fail(
                record,
                AppError(
                    ErrorCode.INTERNAL_ERROR,
                    "An unexpected error occurred while processing this job.",
                ),
            )
        finally:
            await http.aclose()
            await self.storage.delete_tree(work_dir)
            # If the job did not complete, make sure no partial output survives.
            current = await self.store.get(job_id)
            if current is None or current.status != JobStatus.COMPLETED:
                await self.storage.delete_tree(output_dir)

    async def _fail(self, record: JobRecord, exc: AppError) -> None:
        payload = ErrorPayload(
            code=exc.code, message=exc.message, retryable=exc.retryable, details=exc.details or None
        )
        await self.store.fail(record.id, payload)
        log.info("job.failed", job_id=record.id, tool=record.tool, code=exc.code.value)

    # ------------------------------------------------------------------
    async def _resolve_input(
        self, record: JobRecord, tool: Tool, ctx: ToolContext, options: object
    ) -> ToolInput:
        inp = record.input
        if inp.kind == "text":
            return ToolInput(kind=InputKind.TEXT, text=inp.text)

        if inp.kind == "upload":
            assert inp.upload_id is not None
            return ToolInput(kind=InputKind.UPLOAD, files=[await self._load_upload(inp.upload_id)])

        if inp.kind == "uploads":
            assert inp.upload_ids is not None
            if len(inp.upload_ids) > MAX_FILES_PER_JOB:
                raise AppError(
                    ErrorCode.INVALID_OPTIONS,
                    f"At most {MAX_FILES_PER_JOB} files can be processed in one job.",
                )
            files = [await self._load_upload(uid) for uid in inp.upload_ids]
            return ToolInput(kind=InputKind.UPLOADS, files=files)

        assert inp.url is not None
        parsed = parse_url(inp.url, self.settings)
        validated = await validate_and_resolve(parsed.url, self.settings)
        if not tool.spec.fetch_input:
            return ToolInput(kind=InputKind.URL, url=validated)

        extractor = find_extractor(parsed, self.settings)
        if extractor is not None:
            if not tool.spec.accepts_platform_media:
                raise AppError(
                    ErrorCode.TOOL_INPUT_MISMATCH,
                    f"Tool '{tool.spec.id}' cannot be used with {extractor.platform.value} links.",
                )
            if not runtime().has("platform_extractors"):
                raise AppError(
                    ErrorCode.TOOL_UNAVAILABLE, "Platform extraction is disabled on this server."
                )
            format_id = getattr(options, "format", None) or tool.spec.platform_default_format
            await ctx.report("downloading", force=True)

            async def progress(phase: str, pct: float | None, message: str | None) -> None:
                await ctx.report(phase, percent=pct, message=message)

            path = await extractor.download(
                validated,
                format_id=str(format_id),
                dest_dir=ctx.work_dir / "source",
                settings=self.settings,
                progress=progress,
                is_cancelled=ctx.is_cancelled,
                max_bytes=self.settings.max_file_size_bytes,
                timeout=ctx.remaining_seconds,
            )
            analysis = None
            with contextlib.suppress(AppError):
                analysis = await extractor.analyze(validated, self.settings)
            title = analysis.title if analysis and analysis.title else None
            local = describe_local_file(path, filename=f"{title}{path.suffix}" if title else None)
            if local.resource_type == ResourceType.UNKNOWN:
                # Trust the container extension yt-dlp produced (e.g. .mp4/.webm/.m4a).
                from anything_download.detection.mime import (
                    mime_for_extension,
                    resource_type_for_mime,
                )

                mime = mime_for_extension(path.suffix.lstrip("."))
                if mime:
                    local.mime_type = mime
                    local.resource_type = resource_type_for_mime(mime)
            return ToolInput(kind=InputKind.URL, url=validated, files=[local], analysis=analysis)

        await ctx.report("downloading", force=True)

        async def on_bytes(done: int, total: int | None) -> None:
            pct = (done / total * 100.0) if total else None
            await ctx.report("downloading", percent=pct)

        local = await download_to_file(
            ctx.http,
            validated,
            ctx.work_dir / "source",
            settings=self.settings,
            max_bytes=self.settings.max_file_size_bytes,
            on_progress=on_bytes,
            is_cancelled=ctx.is_cancelled,
        )
        return ToolInput(kind=InputKind.URL, url=validated, files=[local])

    async def _load_upload(self, upload_id: str) -> LocalInput:
        try:
            upload_dir = self.storage.upload_dir(upload_id)
        except ValueError as exc:
            raise AppError(
                ErrorCode.UPLOAD_NOT_FOUND, "The uploaded file reference is invalid."
            ) from exc
        record = await self.store.get_upload(upload_id)
        if record is None or not upload_dir.exists():
            raise AppError(
                ErrorCode.UPLOAD_NOT_FOUND,
                "The uploaded file has expired or does not exist. Please upload it again.",
            )
        path = upload_dir / "file"
        if not path.exists():
            raise AppError(
                ErrorCode.UPLOAD_NOT_FOUND,
                "The uploaded file has expired or does not exist. Please upload it again.",
            )
        return LocalInput(
            path=path,
            filename=record.filename,
            mime_type=record.mime_type,
            resource_type=record.resource_type,
            size_bytes=record.size_bytes,
        )

    async def _publish(self, record: JobRecord, output: ToolOutput) -> None:
        file: ResultFile | None = None
        expires_at = result_expiry(self.settings)
        if output.file_path is not None:
            path: Path = output.file_path
            if not path.exists():
                raise AppError(
                    ErrorCode.PROCESSING_FAILED, "The tool reported success but produced no file."
                )
            # Backstop for every tool, not just the ones that stream through ffmpeg.
            if path.stat().st_size > self.settings.max_file_size_bytes:
                path.unlink(missing_ok=True)
                raise AppError(
                    ErrorCode.FILE_TOO_LARGE,
                    f"The result exceeded the {self.settings.max_file_size_mb} MB limit "
                    "and was discarded.",
                )
            output_dir = self.storage.job_dir(record.id)
            if output_dir.resolve() not in path.resolve().parents:
                # Tool wrote into the work dir; move it into the served job directory.
                target = self.storage.resolve_within(output_dir, output.filename or path.name)
                path.replace(target)
                path = target
            file = ResultFile(
                filename=output.filename or path.name,
                mime_type=output.mime_type or "application/octet-stream",
                size_bytes=path.stat().st_size,
                resource_type=output.resource_type,
            )
            await self.store.schedule_expiry(f"job:{record.id}", expires_at)
        result = JobResult(file=file, data=output.data, notes=output.notes)
        updated = await self.store.complete(record.id, result, expires_at if file else None)
        if updated is None:
            # Job was cancelled while finishing: discard output.
            raise JobCancelled()
