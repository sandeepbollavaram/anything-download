"""Output size enforcement.

A source whose duration ffprobe cannot determine (or a pathological encode) is
otherwise bounded only by the wall-clock job timeout, which is long enough to
fill the disk. These tests cover both layers of the cap: ffmpeg is killed while
it runs, and the job runner refuses an oversized result from any tool.
"""

from __future__ import annotations

import contextlib
import os
import sys
import textwrap
from pathlib import Path

import pytest

from anything_download.config import Settings
from anything_download.domain import JobStatus
from anything_download.errors import AppError, ErrorCode
from anything_download.media.ffmpeg import ffmpeg
from tests.conftest import requires_ffmpeg

ONE_MB = 1024 * 1024
CHUNK = 32 * 1024


def _fake_ffmpeg(tmp_path: Path, out_file: Path, *, total_bytes: int) -> str:
    """A stand-in binary that ignores ffmpeg's flags and just writes ``out_file``.

    Lets the watchdog be tested without a real ffmpeg on the host.
    """
    script = tmp_path / "fake_ffmpeg.py"
    script.write_text(
        textwrap.dedent(f"""
            import time
            written = 0
            with open(r"{out_file}", "wb") as fh:
                while written < {total_bytes}:
                    fh.write(b"\\0" * {CHUNK})
                    fh.flush()
                    written += {CHUNK}
                    time.sleep(0.02)
            time.sleep(10)  # outlive the watchdog so the kill is what ends us
        """),
        encoding="utf-8",
    )
    if os.name == "nt":
        launcher = tmp_path / "fake_ffmpeg.bat"
        launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher = tmp_path / "fake_ffmpeg.sh"
        launcher.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8"
        )
        launcher.chmod(0o755)
    return str(launcher)


@pytest.mark.asyncio
async def test_ffmpeg_killed_when_output_exceeds_limit(tmp_path: Path, settings: Settings) -> None:
    out = tmp_path / "big.mp4"
    fake = _fake_ffmpeg(tmp_path, out, total_bytes=2 * ONE_MB)
    patched = settings.model_copy(update={"ffmpeg_bin": fake})

    with pytest.raises(AppError) as exc:
        await ffmpeg(
            ["-i", "input", str(out)],
            settings=patched,
            timeout=30.0,
            output_path=out,
            max_output_bytes=256 * 1024,
        )

    assert exc.value.code == ErrorCode.FILE_TOO_LARGE
    # The partial file must not survive to be served.
    assert not out.exists()


@pytest.mark.asyncio
async def test_ffmpeg_allows_output_under_limit(tmp_path: Path, settings: Settings) -> None:
    out = tmp_path / "small.mp4"
    fake = _fake_ffmpeg(tmp_path, out, total_bytes=128 * 1024)
    patched = settings.model_copy(update={"ffmpeg_bin": fake})

    # The fake sleeps after writing, so the timeout (not the size cap) ends it.
    with pytest.raises(AppError) as exc:
        await ffmpeg(
            ["-i", "input", str(out)],
            settings=patched,
            timeout=3.0,
            output_path=out,
            max_output_bytes=8 * ONE_MB,
        )

    assert exc.value.code == ErrorCode.PROCESSING_TIMEOUT
    assert out.exists(), "a file under the limit must not be deleted by the size cap"


@pytest.mark.asyncio
async def test_runner_rejects_oversized_tool_output(store, storage, settings: Settings) -> None:
    """The runner backstops tools that never go through ffmpeg (pdf, image, browser)."""
    from anything_download.domain import ResourceType
    from anything_download.jobs.models import JobInput, JobRecord
    from anything_download.jobs.runner import JobRunner
    from anything_download.tools.base import ToolOutput

    patched = settings.model_copy(update={"max_file_size_mb": 2})
    runner = JobRunner(store, storage, patched)
    record = JobRecord(id="d" * 32, tool="pdf-merger", input=JobInput(kind="text", text="x"))
    await store.save(record)

    work = storage.create_work_dir(record.id)
    oversized = work / "result.pdf"
    oversized.write_bytes(b"\0" * (3 * ONE_MB))

    with pytest.raises(AppError) as exc:
        await runner._publish(
            record,
            ToolOutput(
                file_path=oversized,
                filename="result.pdf",
                mime_type="application/pdf",
                resource_type=ResourceType.PDF,
            ),
        )

    assert exc.value.code == ErrorCode.FILE_TOO_LARGE
    assert not oversized.exists()
    assert (await store.require(record.id)).status is not JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_runner_publishes_output_under_limit(store, storage, settings: Settings) -> None:
    from anything_download.domain import ResourceType
    from anything_download.jobs.models import JobInput, JobRecord
    from anything_download.jobs.runner import JobRunner
    from anything_download.tools.base import ToolOutput

    runner = JobRunner(store, storage, settings)
    record = JobRecord(
        id="e" * 32,
        tool="pdf-merger",
        input=JobInput(kind="text", text="x"),
        status=JobStatus.RUNNING,
    )
    await store.save(record)

    storage.create_job_dir(record.id)
    work = storage.create_work_dir(record.id)
    small = work / "result.pdf"
    small.write_bytes(b"%PDF-1.4\n" + b"\0" * 2048)

    await runner._publish(
        record,
        ToolOutput(
            file_path=small,
            filename="result.pdf",
            mime_type="application/pdf",
            resource_type=ResourceType.PDF,
        ),
    )

    completed = await store.require(record.id)
    assert completed.status is JobStatus.COMPLETED
    assert completed.result is not None
    assert completed.result.file is not None


def test_size_limit_is_passed_to_ffmpeg_before_the_output_file(tmp_path: Path) -> None:
    from anything_download.media.ffmpeg import _with_size_limit

    out = tmp_path / "out.mp4"
    args = ["-i", "in.mp4", "-c:v", "libx264", str(out)]
    assert _with_size_limit(args, out, 5 * ONE_MB) == [
        "-i",
        "in.mp4",
        "-c:v",
        "libx264",
        "-fs",
        str(5 * ONE_MB),
        str(out),
    ]


def test_size_limit_is_not_added_when_output_is_not_the_last_argument(tmp_path: Path) -> None:
    from anything_download.media.ffmpeg import _with_size_limit

    out = tmp_path / "out.mp4"
    args = [str(out), "-f", "null", "-"]
    assert _with_size_limit(args, out, ONE_MB) == args
    assert _with_size_limit(["-i", "x", str(out)], out, None) == ["-i", "x", str(out)]
    assert _with_size_limit(["-i", "x", str(out)], None, ONE_MB) == ["-i", "x", str(out)]


@requires_ffmpeg
@pytest.mark.asyncio
async def test_real_ffmpeg_output_overshoot_is_bounded(tmp_path: Path, settings: Settings) -> None:
    """With only the once-a-second poll, a raw 320x240 stream written in real time
    (~5.7 MB/s) overshoots a 2 MB cap by megabytes. ``-fs`` must keep it to about a packet."""
    import asyncio

    out = tmp_path / "raw.avi"
    limit = 2 * ONE_MB
    peak = 0

    async def sample() -> None:
        nonlocal peak
        while True:
            with contextlib.suppress(OSError):
                peak = max(peak, out.stat().st_size)
            await asyncio.sleep(0.01)

    sampler = asyncio.create_task(sample())
    try:
        with pytest.raises(AppError) as exc:
            await ffmpeg(
                [
                    "-re",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=size=320x240:rate=25",
                    "-t",
                    "20",
                    "-c:v",
                    "rawvideo",
                    str(out),
                ],
                settings=settings,
                timeout=30.0,
                output_path=out,
                max_output_bytes=limit,
            )
    finally:
        sampler.cancel()

    assert exc.value.code == ErrorCode.FILE_TOO_LARGE
    assert not out.exists()
    assert peak < limit + ONE_MB, f"output reached {peak} bytes against a {limit} byte cap"
