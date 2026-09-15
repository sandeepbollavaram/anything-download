"""Audio tools (FFmpeg based)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.media.ffmpeg import ffmpeg, ffprobe, safe_path
from anything_download.tools.base import (
    InputKind,
    NoOptions,
    Tool,
    ToolContext,
    ToolInput,
    ToolOutput,
    ToolSpec,
)
from anything_download.tools.common import DownloadTool, output_name, stem_of
from anything_download.tools.registry import register

_AUDIO = frozenset({ResourceType.AUDIO, ResourceType.VIDEO})
_URL_UPLOAD = frozenset({InputKind.URL, InputKind.UPLOAD})

AudioFormat = Literal["mp3", "wav", "aac", "m4a", "ogg", "flac"]

_CODECS: dict[str, tuple[list[str], str]] = {
    "mp3": (["-c:a", "libmp3lame"], "audio/mpeg"),
    "wav": (["-c:a", "pcm_s16le"], "audio/wav"),
    "aac": (["-c:a", "aac"], "audio/aac"),
    "m4a": (["-c:a", "aac"], "audio/mp4"),
    "ogg": (["-c:a", "libopus"], "audio/ogg"),
    "flac": (["-c:a", "flac"], "audio/flac"),
}
_LOSSY = {"mp3", "aac", "m4a", "ogg"}


async def _run(ctx: ToolContext, args: list[str], duration: float | None, dest: Path) -> None:
    async def cb(pct: float | None) -> None:
        await ctx.report("processing", percent=pct)

    await ffmpeg(
        args,
        settings=ctx.settings,
        timeout=ctx.remaining_seconds,
        duration=duration,
        on_progress=cb,
        is_cancelled=ctx.is_cancelled,
        output_path=dest,
        max_output_bytes=ctx.settings.max_file_size_bytes,
    )


class ConvertOptions(BaseModel):
    model_config = {"extra": "forbid"}
    target: AudioFormat = "mp3"
    bitrate_kbps: Literal[64, 96, 128, 160, 192, 256, 320] = 192
    format: str = Field(default="audio", description="Platform source format id.")


class AudioConverter(Tool):
    spec = ToolSpec(
        id="audio-converter",
        category="audio",
        capability=Capability.CONVERT,
        inputs=_URL_UPLOAD,
        accepts=_AUDIO,
        options_model=ConvertOptions,
        requires=frozenset({"ffmpeg"}),
        accepts_platform_media=True,
        platform_default_format="audio",
        order=41,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, ConvertOptions)
        info = await ffprobe(source.file.path, ctx.settings)
        if not info.has_audio:
            raise AppError(ErrorCode.FILE_TYPE_UNSUPPORTED, "This file has no audio stream.")
        limit = ctx.settings.max_video_duration_seconds
        if info.duration is not None and info.duration > limit:
            raise AppError(
                ErrorCode.FILE_TOO_LARGE,
                f"This media is longer than the {limit // 60}-minute processing limit.",
            )
        codec_args, mime = _CODECS[options.target]
        dest, name = output_name(ctx, stem_of(source), options.target)
        args = ["-i", safe_path(source.file.path), "-vn", "-map", "0:a:0", *codec_args]
        if options.target in _LOSSY:
            args += ["-b:a", f"{options.bitrate_kbps}k"]
        if options.target == "ogg":
            args += ["-f", "ogg"]
        if options.target == "m4a":
            args += ["-f", "ipod"]
        if options.target == "aac":
            args += ["-f", "adts"]
        args += [safe_path(dest)]
        await _run(ctx, args, info.duration, dest)
        return ToolOutput(
            file_path=dest, filename=name, mime_type=mime, resource_type=ResourceType.AUDIO
        )


class AudioCompressOptions(BaseModel):
    model_config = {"extra": "forbid"}
    level: Literal["light", "medium", "strong"] = "medium"
    format: str = "audio"


class AudioCompressor(Tool):
    spec = ToolSpec(
        id="audio-compressor",
        category="audio",
        capability=Capability.COMPRESS,
        inputs=_URL_UPLOAD,
        accepts=_AUDIO,
        options_model=AudioCompressOptions,
        requires=frozenset({"ffmpeg"}),
        accepts_platform_media=True,
        platform_default_format="audio",
        order=42,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, AudioCompressOptions)
        info = await ffprobe(source.file.path, ctx.settings)
        audio = info.audio
        if audio is None:
            raise AppError(ErrorCode.FILE_TYPE_UNSUPPORTED, "This file has no audio stream.")
        limit = ctx.settings.max_video_duration_seconds
        if info.duration is not None and info.duration > limit:
            raise AppError(
                ErrorCode.FILE_TOO_LARGE,
                f"This media is longer than the {limit // 60}-minute processing limit.",
            )
        bitrate = {"light": "128k", "medium": "96k", "strong": "64k"}[options.level]
        # Keep the family of the input container where sensible; otherwise use MP3.
        if audio.codec_name in {"aac", "alac"} or source.file.mime_type in {
            "audio/mp4",
            "audio/aac",
        }:
            target, codec_args, mime, extra = "m4a", ["-c:a", "aac"], "audio/mp4", ["-f", "ipod"]
        elif audio.codec_name in {"opus", "vorbis"} or source.file.mime_type == "audio/ogg":
            target, codec_args, mime, extra = "ogg", ["-c:a", "libopus"], "audio/ogg", ["-f", "ogg"]
        else:
            target, codec_args, mime, extra = "mp3", ["-c:a", "libmp3lame"], "audio/mpeg", []
        dest, name = output_name(ctx, f"{stem_of(source)}-compressed", target)
        args = [
            "-i",
            safe_path(source.file.path),
            "-vn",
            "-map",
            "0:a:0",
            *codec_args,
            "-b:a",
            bitrate,
            *extra,
            safe_path(dest),
        ]
        await _run(ctx, args, info.duration, dest)
        notes = ["output_not_smaller"] if dest.stat().st_size >= source.file.size_bytes else []
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type=mime,
            resource_type=ResourceType.AUDIO,
            notes=notes,
        )


class AudioMetadata(Tool):
    spec = ToolSpec(
        id="audio-metadata",
        category="audio",
        capability=Capability.EXTRACT_METADATA,
        inputs=_URL_UPLOAD,
        accepts=frozenset({ResourceType.AUDIO}),
        options_model=NoOptions,
        requires=frozenset({"ffmpeg"}),
        output="data",
        order=43,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        info = await ffprobe(source.file.path, ctx.settings)
        data = info.to_dict()
        data["filename"] = source.file.filename
        data["mime_type"] = source.file.mime_type
        data["size_bytes"] = source.file.size_bytes
        return ToolOutput(data=data, resource_type=ResourceType.AUDIO)


register(
    DownloadTool(
        "audio-downloader",
        "audio",
        {ResourceType.AUDIO},
        platform=True,
        order=40,
        platform_default_format="audio",
    )
)
register(AudioConverter())
register(AudioCompressor())
register(AudioMetadata())
