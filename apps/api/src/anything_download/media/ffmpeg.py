"""Safe FFmpeg / FFprobe invocation.

* argument arrays only, never shell strings
* hard timeouts with process kill
* cooperative cancellation
* real progress from ``-progress pipe:1`` when the input duration is known
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NoReturn

from anything_download.config import Settings, get_settings
from anything_download.errors import AppError, ErrorCode
from anything_download.logging import get_logger

log = get_logger(__name__)

# Filenames handed to ffmpeg are always absolute paths we created ourselves; still,
# refuse anything that could be parsed as an option or protocol.
_UNSAFE_PATH = re.compile(r"^-|^[a-zA-Z][a-zA-Z0-9+.-]*:")

# Inputs are always local files we already fetched. Do not let a crafted
# playlist or container open http/https/tcp (SSRF past SafeHttpClient).
# ``pipe`` is required for ``-progress pipe:1``.
SAFE_IO_ARGS: tuple[str, ...] = ("-protocol_whitelist", "file,crypto,data,pipe")


def safe_path(path: Path) -> str:
    text = str(path)
    if _UNSAFE_PATH.match(path.name) or "|" in text:
        raise AppError(ErrorCode.PROCESSING_FAILED, "Refusing to pass an unsafe path to ffmpeg.")
    return text


@dataclass
class StreamInfo:
    index: int
    codec_type: str
    codec_name: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    sample_rate: int | None = None
    channels: int | None = None
    bit_rate: int | None = None
    duration: float | None = None
    language: str | None = None


@dataclass
class ProbeResult:
    format_name: str | None
    duration: float | None
    size: int | None
    bit_rate: int | None
    streams: list[StreamInfo] = field(default_factory=list)
    tags: dict[str, str] = field(default_factory=dict)

    @property
    def video(self) -> StreamInfo | None:
        return next(
            (
                s
                for s in self.streams
                if s.codec_type == "video" and (s.codec_name or "") not in {"mjpeg", "png"}
            ),
            None,
        )

    @property
    def audio(self) -> StreamInfo | None:
        return next((s for s in self.streams if s.codec_type == "audio"), None)

    @property
    def has_video(self) -> bool:
        return self.video is not None

    @property
    def has_audio(self) -> bool:
        return self.audio is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": self.format_name,
            "duration_seconds": self.duration,
            "size_bytes": self.size,
            "bit_rate": self.bit_rate,
            "tags": self.tags,
            "streams": [
                {k: v for k, v in s.__dict__.items() if v is not None} for s in self.streams
            ],
        }


_SAFE_TAGS = {
    "title",
    "artist",
    "album",
    "album_artist",
    "date",
    "genre",
    "track",
    "composer",
    "comment",
    "encoder",
    "creation_time",
    "language",
    "publisher",
    "copyright",
    "description",
    "major_brand",
    "handler_name",
}


async def ffprobe(
    path: Path, settings: Settings | None = None, *, timeout: float = 60.0
) -> ProbeResult:
    settings = settings or get_settings()
    args = [
        settings.ffprobe_bin,
        *SAFE_IO_ARGS,
        "-v",
        "error",
        "-hide_banner",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        "-i",
        safe_path(path),
    ]
    stdout, _stderr, code = await _run(args, timeout=timeout, settings=settings)
    if code != 0:
        raise AppError(
            ErrorCode.FILE_CORRUPT,
            "The media file could not be read. It may be corrupt or in an unsupported format.",
            details={"tool": "ffprobe"},
        )
    try:
        data = json.loads(stdout.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError as exc:
        raise AppError(ErrorCode.FILE_CORRUPT, "ffprobe returned unreadable output.") from exc
    fmt = data.get("format", {}) or {}
    streams: list[StreamInfo] = []
    for s in data.get("streams", []) or []:
        streams.append(
            StreamInfo(
                index=int(s.get("index", len(streams))),
                codec_type=str(s.get("codec_type", "unknown")),
                codec_name=s.get("codec_name"),
                width=_int(s.get("width")),
                height=_int(s.get("height")),
                fps=_parse_rate(s.get("avg_frame_rate") or s.get("r_frame_rate")),
                sample_rate=_int(s.get("sample_rate")),
                channels=_int(s.get("channels")),
                bit_rate=_int(s.get("bit_rate")),
                duration=_float(s.get("duration")),
                language=(s.get("tags") or {}).get("language"),
            )
        )
    tags = {
        k.lower(): str(v)[:500]
        for k, v in (fmt.get("tags") or {}).items()
        if k.lower() in _SAFE_TAGS
    }
    return ProbeResult(
        format_name=fmt.get("format_name"),
        duration=_float(fmt.get("duration")),
        size=_int(fmt.get("size")),
        bit_rate=_int(fmt.get("bit_rate")),
        streams=streams,
        tags=tags,
    )


ProgressCallback = Callable[[float | None], Awaitable[None]]
CancelCheck = Callable[[], Awaitable[bool]]


async def ffmpeg(
    args: Sequence[str],
    *,
    settings: Settings | None = None,
    timeout: float,
    duration: float | None = None,
    on_progress: ProgressCallback | None = None,
    is_cancelled: CancelCheck | None = None,
    output_path: Path | None = None,
    max_output_bytes: int | None = None,
) -> None:
    """Run ffmpeg with ``args`` (everything after the binary name).

    ``duration`` (seconds of expected output) enables real percentage progress.

    ``max_output_bytes`` bounds the *produced* file: without it a source whose
    duration ffprobe could not determine (or a pathological encode) is limited
    only by the wall-clock job timeout, which is long enough to fill the disk.
    It is enforced twice. ffmpeg's own ``-fs`` stops the muxer once the file
    passes the limit, which bounds the overshoot to roughly one packet. The file
    is also polled once a second and the process killed if it grows past the
    limit anyway (``-fs`` is ignored by some outputs, e.g. image sequences);
    that poll alone lets a fast writer overshoot by about a second of output.
    """
    settings = settings or get_settings()
    cmd = [
        settings.ffmpeg_bin,
        *SAFE_IO_ARGS,
        "-hide_banner",
        "-nostdin",
        "-y",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-nostats",
        *_with_thread_limit(
            _with_size_limit(args, output_path, max_output_bytes),
            output_path,
            settings.ffmpeg_threads,
        ),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stderr_chunks: list[bytes] = []

    async def read_stderr() -> None:
        assert proc.stderr is not None
        while True:
            chunk = await proc.stderr.read(4096)
            if not chunk:
                break
            if sum(len(c) for c in stderr_chunks) < 64 * 1024:
                stderr_chunks.append(chunk)

    async def read_progress() -> None:
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode("utf-8", "replace").strip()
            if text.startswith("out_time_us=") or text.startswith("out_time_ms="):
                raw = text.split("=", 1)[1]
                if duration and on_progress and raw.isdigit():
                    pct = min(99.0, (int(raw) / 1_000_000) / duration * 100.0)
                    await on_progress(pct)

    watch_output = max_output_bytes is not None and output_path is not None
    oversized = False

    def _output_size() -> int:
        assert output_path is not None
        try:
            return output_path.stat().st_size
        except OSError:
            return 0  # not created yet, or already gone

    async def watch_cancel() -> None:
        nonlocal oversized
        if is_cancelled is None and not watch_output:
            return
        while True:
            await asyncio.sleep(1.0)
            if is_cancelled is not None and await is_cancelled():
                await _terminate(proc, settings)
                return
            if watch_output and _output_size() > max_output_bytes:  # type: ignore[operator]
                oversized = True
                await _terminate(proc, settings)
                return

    readers = asyncio.gather(read_stderr(), read_progress())
    canceller = asyncio.create_task(watch_cancel())
    try:
        await asyncio.wait_for(proc.wait(), timeout=timeout)
    except TimeoutError as exc:
        await _terminate(proc, settings)
        raise AppError(
            ErrorCode.PROCESSING_TIMEOUT,
            "Processing took too long and was stopped. Try a smaller or shorter file.",
        ) from exc
    except asyncio.CancelledError:
        await _terminate(proc, settings)
        raise
    finally:
        canceller.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await canceller
        with contextlib.suppress(Exception):
            await asyncio.wait_for(readers, timeout=5)

    # Checked before cancellation/returncode: killing for size leaves both misleading.
    if oversized:
        _discard_oversized(output_path, max_output_bytes)
    if is_cancelled is not None and await is_cancelled():
        from anything_download.tools.base import JobCancelled

        raise JobCancelled()
    if proc.returncode != 0:
        err = b"".join(stderr_chunks).decode("utf-8", "replace").strip()
        log.warning("ffmpeg.failed", returncode=proc.returncode, stderr=err[-2000:])
        raise AppError(
            ErrorCode.PROCESSING_FAILED,
            "FFmpeg could not process this file." + (f" ({_short_reason(err)})" if err else ""),
        )
    # ffmpeg can cross the limit between the last poll and a clean exit.
    if watch_output and _output_size() > max_output_bytes:  # type: ignore[operator]
        _discard_oversized(output_path, max_output_bytes)


def _with_thread_limit(args: Sequence[str], output_path: Path | None, threads: int) -> list[str]:
    """Cap the threads each ffmpeg process uses (0 leaves ffmpeg's default: every core).

    -threads is not global in ffmpeg: before an -i it limits that input's
    decoder, before the output file it limits the encoder, and filter graphs have
    their own -filter_threads. All three are set, otherwise concurrent jobs each
    try to saturate every core.
    """
    out = list(args)
    if threads <= 0:
        return out
    n = str(threads)
    limited: list[str] = ["-filter_threads", n]
    for index, arg in enumerate(out):
        is_output = output_path is not None and index == len(out) - 1 and arg == str(output_path)
        if arg == "-i" or is_output:
            limited += ["-threads", n]
        limited.append(arg)
    return limited


def _with_size_limit(
    args: Sequence[str], output_path: Path | None, max_output_bytes: int | None
) -> list[str]:
    """Insert ``-fs`` before the output file, where ffmpeg expects output options."""
    out = list(args)
    if max_output_bytes is None or output_path is None or not out or out[-1] != str(output_path):
        return out
    return [*out[:-1], "-fs", str(max_output_bytes), out[-1]]


def _discard_oversized(output_path: Path | None, max_output_bytes: int | None) -> NoReturn:
    if output_path is not None:
        output_path.unlink(missing_ok=True)
    limit_mb = (max_output_bytes or 0) // (1024 * 1024)
    log.warning("ffmpeg.output_too_large", limit_mb=limit_mb)
    raise AppError(
        ErrorCode.FILE_TOO_LARGE,
        f"Processing produced more than the {limit_mb} MB output limit and was stopped. "
        "Try a shorter file or a smaller output setting.",
    )


def _short_reason(stderr: str) -> str:
    last = stderr.strip().splitlines()[-1] if stderr.strip() else ""
    last = re.sub(r"[A-Za-z]:\\[^\s]+|/[^\s]+", "<path>", last)  # strip local paths
    return last[:160]


async def _terminate(proc: asyncio.subprocess.Process, settings: Settings) -> None:
    if proc.returncode is not None:
        return
    with contextlib.suppress(ProcessLookupError):
        proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=settings.subprocess_grace_seconds)
    except TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            proc.kill()
        with contextlib.suppress(Exception):
            await asyncio.wait_for(proc.wait(), timeout=5)


async def _run(
    args: Sequence[str], *, timeout: float, settings: Settings
) -> tuple[bytes, bytes, int]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdin=asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError as exc:
        await _terminate(proc, settings)
        raise AppError(ErrorCode.PROCESSING_TIMEOUT, "Reading the media file timed out.") from exc
    return stdout, stderr, proc.returncode or 0


def _int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _parse_rate(value: Any) -> float | None:
    if not value or not isinstance(value, str):
        return None
    if "/" in value:
        num, _, den = value.partition("/")
        try:
            n, d = float(num), float(den)
        except ValueError:
            return None
        return round(n / d, 3) if d else None
    return _float(value)
