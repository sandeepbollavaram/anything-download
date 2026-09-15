"""Production-hardening regressions: settings, docs, worker crash, limits."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from anything_download.config import Settings
from anything_download.domain import JobStatus, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.jobs.models import JobInput, JobRecord
from anything_download.media.ffmpeg import ProbeResult, StreamInfo
from anything_download.tools.base import InputKind, LocalInput, ToolInput
from anything_download.tools.video import _probe
from anything_download.workers.worker import Worker


def test_production_refuses_private_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AD_ENV", "production")
    monkeypatch.setenv("AD_ALLOW_PRIVATE_TARGETS", "true")
    from anything_download import config

    config.reset_settings_cache()
    with pytest.raises(ValidationError):
        Settings()


def test_production_disables_docs_unless_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    from anything_download import config

    monkeypatch.setenv("AD_ENV", "production")
    monkeypatch.setenv("AD_ALLOW_PRIVATE_TARGETS", "false")
    monkeypatch.delenv("AD_ENABLE_DOCS", raising=False)
    config.reset_settings_cache()
    assert Settings().enable_docs is False

    monkeypatch.setenv("AD_ENABLE_DOCS", "true")
    config.reset_settings_cache()
    assert Settings().enable_docs is True


def test_docs_disabled_when_flag_false(settings, redis) -> None:
    settings.enable_docs = False
    from anything_download.api.app import create_app

    app = create_app(settings, redis_client=redis)
    assert app.docs_url is None
    assert app.openapi_url is None


@pytest.mark.asyncio
async def test_worker_crash_fails_job(store, storage, settings) -> None:
    record = JobRecord(
        id="a" * 32,
        tool="qr-generator",
        input=JobInput(kind="text", text="x"),
    )
    await store.create(record)
    worker = Worker(store, storage, settings, worker_id="crash-test")

    async def boom(_job_id: str) -> None:
        raise RuntimeError("simulated crash")

    worker.process_one = boom  # type: ignore[method-assign]
    await worker._process(record.id)
    got = await store.require(record.id)
    assert got.status == JobStatus.FAILED
    assert got.error is not None
    assert got.error.retryable is True


@pytest.mark.asyncio
async def test_write_stream_enforces_limit_minus_at_plus(storage, tmp_path: Path) -> None:
    destination = tmp_path / "bounded.bin"
    limit = 16

    async def chunks(size: int) -> AsyncIterator[bytes]:
        yield b"a" * size

    assert await storage.write_stream(destination, chunks(limit - 1), max_bytes=limit) == limit - 1
    assert await storage.write_stream(destination, chunks(limit), max_bytes=limit) == limit
    with pytest.raises(ValueError, match="too large"):
        await storage.write_stream(destination, chunks(limit + 1), max_bytes=limit)
    assert not destination.with_suffix(".bin.part").exists()


@pytest.mark.asyncio
async def test_video_duration_over_limit_is_rejected(
    monkeypatch: pytest.MonkeyPatch, settings, storage, tmp_path: Path
) -> None:
    async def fake_probe(_path: Path, _settings: Settings) -> ProbeResult:
        return ProbeResult(
            format_name="mp4",
            duration=float(settings.max_video_duration_seconds + 1),
            size=1024,
            bit_rate=None,
            streams=[StreamInfo(index=0, codec_type="video", codec_name="h264")],
        )

    monkeypatch.setattr("anything_download.tools.video.ffprobe", fake_probe)
    from tests.unit.test_tools_and_cleanup import _ctx

    source = ToolInput(
        kind=InputKind.UPLOAD,
        files=[
            LocalInput(
                path=tmp_path / "clip.mp4",
                filename="clip.mp4",
                mime_type="video/mp4",
                resource_type=ResourceType.VIDEO,
                size_bytes=1024,
            )
        ],
    )
    with pytest.raises(AppError) as exc:
        await _probe(_ctx(settings, storage), source)
    assert exc.value.code == ErrorCode.FILE_TOO_LARGE


@pytest.mark.asyncio
async def test_video_duration_at_limit_is_allowed(
    monkeypatch: pytest.MonkeyPatch, settings, storage, tmp_path: Path
) -> None:
    async def fake_probe(_path: Path, _settings: Settings) -> ProbeResult:
        return ProbeResult(
            format_name="mp4",
            duration=float(settings.max_video_duration_seconds),
            size=1024,
            bit_rate=None,
            streams=[StreamInfo(index=0, codec_type="video", codec_name="h264")],
        )

    monkeypatch.setattr("anything_download.tools.video.ffprobe", fake_probe)
    from tests.unit.test_tools_and_cleanup import _ctx

    source = ToolInput(
        kind=InputKind.UPLOAD,
        files=[
            LocalInput(
                path=tmp_path / "clip.mp4",
                filename="clip.mp4",
                mime_type="video/mp4",
                resource_type=ResourceType.VIDEO,
                size_bytes=1024,
            )
        ],
    )
    info = await _probe(_ctx(settings, storage), source)
    assert info.duration == settings.max_video_duration_seconds


def test_ffmpeg_refuses_network_protocols() -> None:
    from anything_download.media.ffmpeg import SAFE_IO_ARGS

    assert SAFE_IO_ARGS == ("-protocol_whitelist", "file,crypto,data,pipe")
    assert "http" not in SAFE_IO_ARGS[1]
    assert "https" not in SAFE_IO_ARGS[1]
    assert "tcp" not in SAFE_IO_ARGS[1]


@pytest.mark.asyncio
async def test_reap_stale_workers_fails_in_flight_job(store) -> None:
    from anything_download.jobs.store import processing_key

    record = JobRecord(
        id="c" * 32,
        tool="qr-generator",
        input=JobInput(kind="text", text="x"),
        status=JobStatus.RUNNING,
    )
    await store.save(record)
    await store.redis.lpush(processing_key("dead-worker"), record.id)
    failed = await store.reap_stale_workers()
    assert record.id in failed
    got = await store.require(record.id)
    assert got.status == JobStatus.FAILED
    assert got.error is not None
    assert got.error.retryable is True


@pytest.mark.asyncio
async def test_dequeue_drops_missing_job_ids(store) -> None:
    await store.redis.lpush("ad:queue", "d" * 32)
    got = await store.dequeue("worker-a", timeout=1)
    assert got is None


@pytest.mark.asyncio
async def test_browser_policy_blocks_unusual_loopback_and_re_resolves(
    settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    from anything_download.media.browser import _HostPolicy

    policy = _HostPolicy(settings)
    assert await policy.allowed("http://127.0.0.1/") is False
    assert await policy.allowed("http://2130706433/") is False
    assert await policy.allowed("http://127.1/") is False

    calls = {"n": 0}

    async def fake_resolve(host: str, port: int, *, timeout: float = 3.0) -> tuple[str, ...]:
        calls["n"] += 1
        return ("93.184.216.34",)

    monkeypatch.setattr("anything_download.media.browser.resolve_host", fake_resolve)
    assert await policy.allowed("https://cdn.example/a") is True
    assert await policy.allowed("https://cdn.example/b") is True
    assert calls["n"] == 2


def test_log_message_redacts_urls() -> None:
    from anything_download.logging import _redact_processor

    event = _redact_processor(
        None,
        "info",
        {"message": "fetch https://cdn.example/video.m3u8?token=secret"},
    )
    assert "token=secret" not in event["message"]
    assert "cdn.example" in event["message"]
