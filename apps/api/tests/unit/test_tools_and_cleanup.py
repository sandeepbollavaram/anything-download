"""Tool and cleanup unit tests using isolated storage and fakeredis."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pikepdf
import pytest
from PIL import Image

from anything_download.domain import JobStatus, ResourceType
from anything_download.jobs.models import JobInput, JobRecord, JobResult, ResultFile, UploadRecord
from anything_download.jobs.store import result_expiry
from anything_download.tools.base import InputKind, LocalInput, ToolContext, ToolInput
from anything_download.tools.image import ImageToWebp, WebpOptions
from anything_download.tools.pdf import PdfMerger, PdfSplitOptions, PdfSplitter, PdfToText
from anything_download.tools.registry import all_tools, get_tool
from anything_download.tools.utility import QrGenerateOptions, QrGenerator
from anything_download.workers.cleanup import Cleaner


def _png(path: Path, color: tuple[int, int, int] = (10, 20, 30)) -> Path:
    Image.new("RGB", (40, 24), color).save(path, format="PNG")
    return path


def _pdf(path: Path, pages: int = 2) -> Path:
    pdf = pikepdf.Pdf.new()
    for _ in range(pages):
        pdf.add_blank_page(page_size=(200, 200))
    pdf.save(path)
    pdf.close()
    return path


def _local(path: Path, resource: ResourceType, mime: str) -> LocalInput:
    return LocalInput(
        path=path,
        filename=path.name,
        mime_type=mime,
        resource_type=resource,
        size_bytes=path.stat().st_size,
    )


def _ctx(settings, storage, job_id: str = "b" * 32) -> ToolContext:
    work = storage.create_work_dir(job_id)
    out = storage.create_job_dir(job_id)

    async def report(progress) -> None:
        return None

    async def cancelled() -> bool:
        return False

    return ToolContext(
        job_id=job_id,
        settings=settings,
        storage=storage,
        work_dir=work,
        output_dir=out,
        http=None,  # type: ignore[arg-type]
        report=report,
        is_cancelled=cancelled,
    )


def test_registry_has_expected_tools() -> None:
    ids = {t.spec.id for t in all_tools()}
    expected = {
        "video-downloader",
        "video-to-mp3",
        "video-to-wav",
        "video-to-mp4",
        "video-compressor",
        "video-to-gif",
        "video-thumbnail",
        "video-metadata",
        "image-downloader",
        "image-compressor",
        "image-converter",
        "image-resizer",
        "image-to-webp",
        "image-to-pdf",
        "pdf-downloader",
        "pdf-compressor",
        "pdf-merger",
        "pdf-splitter",
        "pdf-to-text",
        "pdf-to-images",
        "url-to-pdf",
        "audio-downloader",
        "audio-converter",
        "audio-compressor",
        "audio-metadata",
        "url-analyzer",
        "webpage-resource-extractor",
        "image-url-extractor",
        "website-image-gallery",
        "website-pdf-finder",
        "website-video-finder",
        "website-audio-finder",
        "url-metadata",
        "favicon-downloader",
        "qr-generator",
        "qr-reader",
        "webpage-screenshot",
        "file-downloader",
    }
    assert expected <= ids
    assert get_tool("image-compressor").spec.id == "image-compressor"


@pytest.mark.asyncio
async def test_image_to_webp(settings, storage, tmp_path: Path) -> None:
    src = _png(tmp_path / "in.png")
    ctx = _ctx(settings, storage, "c" * 32)
    out = await ImageToWebp().run(
        ctx,
        ToolInput(kind=InputKind.UPLOAD, files=[_local(src, ResourceType.IMAGE, "image/png")]),
        WebpOptions(quality=70),
    )
    assert out.file_path is not None and out.file_path.exists()
    assert out.mime_type == "image/webp"
    assert out.file_path.read_bytes()[8:12] == b"WEBP"


@pytest.mark.asyncio
async def test_qr_generator(settings, storage) -> None:
    ctx = _ctx(settings, storage, "d" * 32)
    out = await QrGenerator().run(
        ctx,
        ToolInput(kind=InputKind.TEXT, text="hello-anything-download"),
        QrGenerateOptions(format="png", scale=5),
    )
    assert out.file_path is not None
    assert out.file_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.asyncio
async def test_pdf_merge_split_text(settings, storage, tmp_path: Path) -> None:
    a = _pdf(tmp_path / "a.pdf", 1)
    b = _pdf(tmp_path / "b.pdf", 2)
    ctx = _ctx(settings, storage, "e" * 32)
    merged = await PdfMerger().run(
        ctx,
        ToolInput(
            kind=InputKind.UPLOADS,
            files=[
                _local(a, ResourceType.PDF, "application/pdf"),
                _local(b, ResourceType.PDF, "application/pdf"),
            ],
        ),
        PdfMerger.spec.options_model(),
    )
    assert merged.data == {"pages": 3, "files": 2}

    split_ctx = _ctx(settings, storage, "f" * 32)
    split = await PdfSplitter().run(
        split_ctx,
        ToolInput(
            kind=InputKind.UPLOAD,
            files=[_local(merged.file_path, ResourceType.PDF, "application/pdf")],
        ),
        PdfSplitOptions(mode="ranges", pages="2-3"),
    )
    assert split.data == {"pages": 2}

    text_ctx = _ctx(settings, storage, "1" * 32)
    text = await PdfToText().run(
        text_ctx,
        ToolInput(
            kind=InputKind.UPLOAD,
            files=[_local(a, ResourceType.PDF, "application/pdf")],
        ),
        PdfToText.spec.options_model(),
    )
    assert text.notes == ["no_text_layer"]
    assert text.file_path is not None and text.file_path.exists()


@pytest.mark.asyncio
async def test_cleanup_expires_job_and_upload(settings, store, storage) -> None:
    job_id = "2" * 32
    upload_id = "3" * 32
    job_dir = storage.create_job_dir(job_id)
    (job_dir / "out.bin").write_bytes(b"result")
    upload_dir = storage.create_upload_dir(upload_id)
    (upload_dir / "file").write_bytes(b"upload")

    past = datetime.now(UTC) - timedelta(minutes=5)
    record = JobRecord(
        id=job_id,
        tool="qr-generator",
        input=JobInput(kind="text", text="x"),
        status=JobStatus.COMPLETED,
        expires_at=past,
        result=JobResult(
            file=ResultFile(filename="out.bin", mime_type="application/octet-stream", size_bytes=6)
        ),
    )
    await store.save(record)
    await store.schedule_expiry(f"job:{job_id}", past)
    await store.save_upload(
        UploadRecord(
            id=upload_id,
            filename="file.bin",
            mime_type="application/octet-stream",
            size_bytes=6,
            resource_type=ResourceType.DOCUMENT,
            expires_at=past,
        )
    )
    # save_upload schedules expiry in the future relative to now if clock is used;
    # force the score into the past.
    await store.schedule_expiry(f"upload:{upload_id}", past)

    report = await Cleaner(store, storage, settings).run_once()
    assert report.jobs_expired >= 1
    assert report.uploads_expired >= 1
    assert not job_dir.exists()
    assert not upload_dir.exists()
    updated = await store.get(job_id)
    assert updated is None or updated.status == JobStatus.EXPIRED


@pytest.mark.asyncio
async def test_cleanup_does_not_expire_data_only_completed_jobs(settings, store, storage) -> None:
    job_id = "4" * 32
    job_dir = storage.create_job_dir(job_id)
    import os
    import time

    os.utime(job_dir, (time.time() - settings.result_ttl_seconds - 10,) * 2)
    record = JobRecord(
        id=job_id,
        tool="url-analyzer",
        input=JobInput(kind="url", url="https://example.com/"),
        status=JobStatus.COMPLETED,
        result=JobResult(data={"title": "Example"}),
    )
    await store.save(record)
    report = await Cleaner(store, storage, settings).run_once()
    kept = await store.require(job_id)
    assert kept.status == JobStatus.COMPLETED
    assert kept.result is not None
    assert kept.result.data == {"title": "Example"}
    assert not job_dir.exists()
    assert report.orphans_removed >= 1


def test_result_expiry_uses_settings(settings) -> None:
    expiry = result_expiry(settings)
    delta = expiry - datetime.now(UTC)
    assert 29 * 60 <= delta.total_seconds() <= 31 * 60
