"""Global resource limits: storage pressure, request bodies, ffmpeg threads.

Disk pressure is simulated by patching the free-space measurement; nothing here
writes more than a few megabytes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import AsyncClient

from anything_download.config import Settings
from anything_download.errors import AppError, ErrorCode
from anything_download.storage.guard import StorageGuard

MB = 1024 * 1024
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _free(monkeypatch: pytest.MonkeyPatch, *values: int) -> None:
    """Patch free space; with several values, each call consumes one (the last repeats)."""
    queue = list(values)

    def fake(self: StorageGuard) -> int:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    monkeypatch.setattr(StorageGuard, "free_bytes", fake)


def _listing(path: Path) -> set[str]:
    return {p.name for p in path.iterdir()} if path.exists() else set()


# -- guard policy ---------------------------------------------------------------------
def test_guard_refuses_below_free_space_floor(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    guard = StorageGuard(settings.model_copy(update={"min_free_disk_mb": 100}), tmp_path)
    _free(monkeypatch, 150 * MB)
    guard.require()  # 150 MB free against a 100 MB floor
    with pytest.raises(AppError) as exc:
        guard.require(incoming_bytes=60 * MB)  # would leave 90 MB
    assert exc.value.code is ErrorCode.STORAGE_FULL
    assert exc.value.status_code == 503
    assert exc.value.retryable
    assert exc.value.retry_after


def test_guard_enforces_directory_quota(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    capped = settings.model_copy(update={"min_free_disk_mb": 0, "max_storage_mb": 1})
    guard = StorageGuard(capped, tmp_path)
    _free(monkeypatch, 10_000 * MB)
    (tmp_path / "a").write_bytes(b"\0" * (600 * 1024))
    guard.require(incoming_bytes=300 * 1024)  # 600 KB + 300 KB fits in 1 MB
    with pytest.raises(AppError):
        guard.require(incoming_bytes=600 * 1024)


def test_quota_measurement_is_cached(settings: Settings, tmp_path: Path) -> None:
    guard = StorageGuard(settings.model_copy(update={"max_storage_mb": 1}), tmp_path)
    (tmp_path / "a").write_bytes(b"\0" * 1000)
    assert guard.used_bytes() == 1000
    (tmp_path / "b").write_bytes(b"\0" * 1000)
    # Re-walking the storage tree on every request would itself be a DoS vector.
    assert guard.used_bytes() == 1000


def test_unreadable_filesystem_fails_closed(settings: Settings, tmp_path: Path) -> None:
    guard = StorageGuard(settings.model_copy(update={"min_free_disk_mb": 1}), tmp_path / "missing")
    assert guard.free_bytes() == 0
    with pytest.raises(AppError):
        guard.require()


# -- API enforcement ------------------------------------------------------------------
@pytest.mark.asyncio
async def test_upload_refused_under_disk_pressure(
    api_client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    uploads_dir = settings.storage_dir / "uploads"
    before = _listing(uploads_dir)
    _free(monkeypatch, settings.min_free_disk_bytes - 1)
    response = await api_client.post(
        "/api/v1/uploads", content=PNG_MAGIC + b"\0" * 64, headers={"X-File-Name": "a.png"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_FULL"
    assert response.headers["retry-after"]
    assert _listing(uploads_dir) == before


@pytest.mark.asyncio
async def test_streaming_upload_aborted_when_disk_fills_mid_stream(
    api_client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from anything_download.api.routes import uploads

    # Tests cap uploads at 5 MB; check space every megabyte so the check is reached.
    monkeypatch.setattr(uploads, "_SPACE_CHECK_BYTES", MB)
    uploads_dir = settings.storage_dir / "uploads"
    before = _listing(uploads_dir)
    floor = settings.min_free_disk_bytes
    # Plenty of space when the request starts; below the floor at the first in-stream check.
    _free(monkeypatch, floor + 1000 * MB, floor - 1)

    async def body() -> AsyncIterator[bytes]:
        # No Content-Length, so the up-front check cannot know how big this will be.
        yield PNG_MAGIC
        for _ in range(12):
            yield b"\0" * MB

    response = await api_client.post(
        "/api/v1/uploads", content=body(), headers={"X-File-Name": "big.png"}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_FULL"
    assert _listing(uploads_dir) == before, "the partial upload must be deleted"


@pytest.mark.asyncio
async def test_job_creation_refused_under_disk_pressure(
    api_client: AsyncClient, redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    from anything_download.jobs.store import QUEUE_KEY

    _free(monkeypatch, 0)
    response = await api_client.post(
        "/api/v1/jobs", json={"tool": "qr-generator", "input": {"kind": "text", "text": "x"}}
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "STORAGE_FULL"
    assert await redis.llen(QUEUE_KEY) == 0


@pytest.mark.asyncio
async def test_admitted_job_does_not_start_under_disk_pressure(
    api_client: AsyncClient,
    settings: Settings,
    store,
    storage,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from anything_download.workers.worker import Worker

    created = await api_client.post(
        "/api/v1/jobs", json={"tool": "qr-generator", "input": {"kind": "text", "text": "x"}}
    )
    job_id = created.json()["id"]
    _free(monkeypatch, 0)  # the disk fills after the job was admitted
    await Worker(store, storage, settings, worker_id="t").process_one(job_id)
    job = (await api_client.get(f"/api/v1/jobs/{job_id}")).json()
    assert job["status"] == "FAILED"
    assert job["error"]["code"] == "STORAGE_FULL"
    assert job["error"]["retryable"] is True


@pytest.mark.asyncio
async def test_ready_reports_storage_pressure_without_failing(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _free(monkeypatch, 0)
    response = await api_client.get("/api/v1/ready")
    # Status polling and downloads must keep working under pressure.
    assert response.status_code == 200
    assert response.json()["checks"]["storage_space"] is False
    metrics = (await api_client.get("/api/v1/metrics")).json()["metrics"]
    assert metrics["storage_pressure"] == 1.0


# -- request bodies -------------------------------------------------------------------
@pytest.mark.asyncio
async def test_oversized_json_body_refused(api_client: AsyncClient, settings: Settings) -> None:
    padding = "a" * (settings.max_request_body_kb * 1024 + 10)
    response = await api_client.post(
        "/api/v1/analyze", json={"url": "https://example.com/", "pad": padding}
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_chunked_oversized_body_refused(api_client: AsyncClient, settings: Settings) -> None:
    async def body() -> AsyncIterator[bytes]:
        yield b'{"tool": "qr-generator", "input": {"kind": "text", "text": "'
        for _ in range(settings.max_request_body_kb + 8):
            yield b"a" * 1024
        yield b'"}}'

    response = await api_client.post(
        "/api/v1/jobs", content=body(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_small_bodies_and_uploads_unaffected(
    api_client: AsyncClient, settings: Settings
) -> None:
    reached = await api_client.post("/api/v1/analyze", json={"url": "javascript:x"})
    assert reached.status_code == 400  # got past the limiter to the handler
    larger_than_json_limit = PNG_MAGIC + b"\0" * (settings.max_request_body_kb * 1024 * 2)
    uploaded = await api_client.post(
        "/api/v1/uploads", content=larger_than_json_limit, headers={"X-File-Name": "b.png"}
    )
    assert uploaded.status_code != 413, "the streaming upload endpoint has its own limit"


# -- ffmpeg threads -------------------------------------------------------------------
def test_ffmpeg_thread_cap_covers_decoders_encoder_and_filters(tmp_path: Path) -> None:
    from anything_download.media.ffmpeg import _with_thread_limit

    out = tmp_path / "o.mp4"
    args = ["-i", "a.mp4", "-i", "b.mp3", "-c:v", "libx264", str(out)]
    limited = _with_thread_limit(args, out, 2)
    assert limited[:2] == ["-filter_threads", "2"]
    assert limited.count("-threads") == 3
    assert limited[-3:] == ["-threads", "2", str(out)]
    assert limited.index("-threads") < limited.index("-i")
    assert _with_thread_limit(args, out, 0) == args
