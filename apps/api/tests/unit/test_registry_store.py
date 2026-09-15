"""Tool registry / capability resolution and the job store state machine."""

from datetime import UTC, datetime, timedelta

import pytest

from anything_download.domain import Capability, JobStatus, ResourceType
from anything_download.errors import AppError, ErrorCode, ErrorPayload
from anything_download.jobs.models import JobInput, JobRecord, JobResult, ResultFile
from anything_download.jobs.store import JobStore
from anything_download.tools.base import InputKind
from anything_download.tools.registry import (
    all_tools,
    capabilities_for,
    get_tool,
    tool_view,
    tools_for,
)


def test_every_tool_has_unique_id_and_schema() -> None:
    tools = all_tools()
    ids = [t.spec.id for t in tools]
    assert len(ids) == len(set(ids))
    assert len(ids) >= 38
    for t in tools:
        view = tool_view(t)
        assert view.options_schema["type"] == "object"
        assert view.inputs
        assert view.category in {"video", "image", "pdf", "audio", "web", "utility"}


def test_capabilities_for_types() -> None:
    video_url = {
        t.spec.id for t in tools_for(ResourceType.VIDEO, InputKind.URL, only_available=False)
    }
    assert {
        "video-downloader",
        "video-to-mp3",
        "video-compressor",
        "video-to-gif",
        "video-metadata",
    } <= video_url
    assert "image-compressor" not in video_url

    image_upload = {t.spec.id for t in tools_for(ResourceType.IMAGE, InputKind.UPLOAD)}
    assert {
        "image-compressor",
        "image-converter",
        "image-resizer",
        "image-to-webp",
        "image-to-pdf",
        "qr-reader",
    } <= image_upload
    assert "image-downloader" not in image_upload  # download is URL-only

    pdf_upload = {t.spec.id for t in tools_for(ResourceType.PDF, InputKind.UPLOAD)}
    assert {"pdf-compressor", "pdf-splitter", "pdf-to-text", "pdf-to-images"} <= pdf_upload
    assert "pdf-merger" in {t.spec.id for t in tools_for(ResourceType.PDF, InputKind.UPLOADS)}

    web = {t.spec.id for t in tools_for(ResourceType.WEBPAGE, InputKind.URL)}
    assert {
        "webpage-resource-extractor",
        "website-image-gallery",
        "url-metadata",
        "favicon-downloader",
    } <= web
    assert "webpage-screenshot" not in web  # browser disabled in tests
    assert "webpage-screenshot" in {
        t.spec.id for t in tools_for(ResourceType.WEBPAGE, InputKind.URL, only_available=False)
    }

    unknown = {t.spec.id for t in tools_for(ResourceType.UNKNOWN, InputKind.URL)}
    assert unknown == {"file-downloader", "url-analyzer"}

    platform = {
        t.spec.id
        for t in tools_for(
            ResourceType.VIDEO, InputKind.URL, platform_media=True, only_available=False
        )
    }
    assert "video-downloader" in platform and "audio-downloader" in platform
    assert "image-downloader" not in platform

    caps = capabilities_for(tools_for(ResourceType.VIDEO, InputKind.URL, only_available=False))
    assert caps[0] == Capability.DOWNLOAD
    assert Capability.EXTRACT_AUDIO in caps


def test_unknown_tool() -> None:
    with pytest.raises(AppError) as exc:
        get_tool("nope")
    assert exc.value.code == ErrorCode.TOOL_NOT_FOUND


def test_options_validation() -> None:
    tool = get_tool("image-resizer")
    with pytest.raises(AppError) as exc:
        tool.validate_options({})
    assert exc.value.code == ErrorCode.INVALID_OPTIONS
    with pytest.raises(AppError):
        tool.validate_options({"width": 100, "bogus": 1})
    opts = tool.validate_options({"width": 100})
    assert getattr(opts, "width") == 100


# --------------------------------------------------------------------------- job store
def _record(tool: str = "image-compressor") -> JobRecord:
    return JobRecord(id="a" * 32, tool=tool, input=JobInput(kind="upload", upload_id="b" * 32))


async def test_job_lifecycle(store: JobStore) -> None:
    rec = await store.create(_record())
    assert rec.status == JobStatus.QUEUED
    assert await store.queue_depth() == 1

    job_id = await store.dequeue("w1", timeout=1)
    assert job_id == rec.id
    running = await store.transition(job_id, [JobStatus.QUEUED], JobStatus.RUNNING)
    assert running is not None and running.status == JobStatus.RUNNING

    # Invalid transition is rejected
    assert await store.transition(job_id, [JobStatus.QUEUED], JobStatus.RUNNING) is None

    expires = datetime.now(UTC) + timedelta(minutes=30)
    done = await store.complete(
        job_id,
        JobResult(file=ResultFile(filename="x.jpg", mime_type="image/jpeg", size_bytes=10)),
        expires,
    )
    assert done is not None and done.status == JobStatus.COMPLETED
    assert done.public().result_url == f"/api/v1/jobs/{job_id}/result"

    expired = await store.mark_expired(job_id)
    assert expired is not None and expired.status == JobStatus.EXPIRED and expired.result is None
    metrics = await store.metrics_snapshot()
    assert metrics["jobs_created_total"] == 1
    assert metrics["jobs_completed_total"] == 1
    assert metrics["jobs_expired_total"] == 1


async def test_cancel_queued(store: JobStore) -> None:
    rec = await store.create(_record())
    cancelled = await store.request_cancel(rec.id)
    assert cancelled.status == JobStatus.CANCELLED
    assert await store.queue_depth() == 0
    with pytest.raises(AppError) as exc:
        await store.request_cancel(rec.id)
    assert exc.value.code == ErrorCode.JOB_NOT_CANCELLABLE


async def test_cancel_running_is_cooperative(store: JobStore) -> None:
    rec = await store.create(_record())
    await store.dequeue("w1", timeout=1)
    await store.transition(rec.id, [JobStatus.QUEUED], JobStatus.RUNNING)
    result = await store.request_cancel(rec.id)
    assert result.status == JobStatus.RUNNING  # worker will observe the flag
    assert await store.is_cancel_requested(rec.id)
    marked = await store.mark_cancelled(rec.id)
    assert marked is not None and marked.status == JobStatus.CANCELLED
    # A late completion must not overwrite the cancellation
    assert await store.complete(rec.id, JobResult(), None) is None


async def test_fail_and_missing(store: JobStore) -> None:
    rec = await store.create(_record())
    failed = await store.fail(rec.id, ErrorPayload(code=ErrorCode.PROCESSING_FAILED, message="x"))
    assert failed is not None and failed.status == JobStatus.FAILED
    assert failed.error is not None and failed.error.code == ErrorCode.PROCESSING_FAILED
    assert await store.get("f" * 32) is None
    with pytest.raises(AppError) as exc:
        await store.require("f" * 32)
    assert exc.value.code == ErrorCode.JOB_NOT_FOUND


async def test_queue_full(store: JobStore, monkeypatch: pytest.MonkeyPatch) -> None:
    store.settings = store.settings.model_copy(update={"max_queue_depth": 1})
    await store.create(_record())
    with pytest.raises(AppError) as exc:
        await store.create(JobRecord(id="c" * 32, tool="x", input=JobInput(kind="text", text="hi")))
    assert exc.value.code == ErrorCode.QUEUE_FULL
    assert exc.value.retry_after == 60


async def test_reap_stale_worker(store: JobStore) -> None:
    rec = await store.create(_record())
    await store.dequeue("dead-worker", timeout=1)
    await store.transition(rec.id, [JobStatus.QUEUED], JobStatus.RUNNING)
    # No heartbeat for "dead-worker" -> job should be failed
    failed = await store.reap_stale_workers()
    assert failed == [rec.id]
    got = await store.get(rec.id)
    assert (
        got is not None
        and got.status == JobStatus.FAILED
        and got.error is not None
        and got.error.retryable
    )

    # A live worker's jobs are left alone
    rec2 = await store.create(
        JobRecord(id="d" * 32, tool="x", input=JobInput(kind="text", text="hi"))
    )
    await store.dequeue("alive", timeout=1)
    await store.heartbeat("alive", 60)
    assert await store.reap_stale_workers() == []
    assert (await store.require(rec2.id)).status == JobStatus.QUEUED


async def test_expiry_index(store: JobStore) -> None:
    past = datetime.now(UTC) - timedelta(minutes=1)
    future = datetime.now(UTC) + timedelta(minutes=10)
    await store.schedule_expiry("job:" + "1" * 32, past)
    await store.schedule_expiry("job:" + "2" * 32, future)
    due = await store.due_expiries()
    assert due == ["job:" + "1" * 32]
    await store.unschedule_expiry(due[0])
    assert await store.due_expiries() == []
