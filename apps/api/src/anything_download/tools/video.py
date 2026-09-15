"""Video tools (FFmpeg based)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.media.ffmpeg import ProbeResult, ffmpeg, ffprobe, safe_path
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

_MEDIA = frozenset({ResourceType.VIDEO})
_AV = frozenset({ResourceType.VIDEO, ResourceType.AUDIO})
_URL_UPLOAD = frozenset({InputKind.URL, InputKind.UPLOAD})


async def _probe(ctx: ToolContext, source: ToolInput) -> ProbeResult:
    local = source.file
    info = await ffprobe(local.path, ctx.settings)
    if not info.streams:
        raise AppError(ErrorCode.FILE_CORRUPT, "No media streams were found in this file.")
    limit = ctx.settings.max_video_duration_seconds
    if info.duration is not None and info.duration > limit:
        raise AppError(
            ErrorCode.FILE_TOO_LARGE,
            f"This media is longer than the {limit // 60}-minute processing limit.",
        )
    return info


def _progress(ctx: ToolContext, phase: str = "processing"):  # type: ignore[no-untyped-def]
    async def cb(pct: float | None) -> None:
        await ctx.report(phase, percent=pct)

    return cb


async def _run_ffmpeg(
    ctx: ToolContext, args: list[str], *, dest: Path, duration: float | None
) -> None:
    await ffmpeg(
        args,
        settings=ctx.settings,
        timeout=ctx.remaining_seconds,
        duration=duration,
        on_progress=_progress(ctx),
        is_cancelled=ctx.is_cancelled,
        output_path=dest,
        max_output_bytes=ctx.settings.max_file_size_bytes,
    )


# --------------------------------------------------------------------------
class AudioExtractOptions(BaseModel):
    model_config = {"extra": "forbid"}
    bitrate_kbps: Literal[96, 128, 192, 256, 320] = 192
    format: str = Field(
        default="audio", description="Platform source format id (audio-only by default)."
    )


class _VideoToAudio(Tool):
    def __init__(self, tool_id: str, codec: str, ext: str, mime: str, order: int) -> None:
        self.codec, self.ext, self.mime = codec, ext, mime
        self.spec = ToolSpec(
            id=tool_id,
            category="video",
            capability=Capability.EXTRACT_AUDIO,
            inputs=_URL_UPLOAD,
            accepts=_AV,
            options_model=AudioExtractOptions,
            requires=frozenset({"ffmpeg"}),
            accepts_platform_media=True,
            platform_default_format="audio",
            order=order,
        )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, AudioExtractOptions)
        info = await _probe(ctx, source)
        if not info.has_audio:
            raise AppError(ErrorCode.PROCESSING_FAILED, "This video has no audio track to extract.")
        dest, name = output_name(ctx, stem_of(source), self.ext)
        args = ["-i", safe_path(source.file.path), "-vn", "-map", "0:a:0"]
        if self.codec == "libmp3lame":
            args += ["-c:a", "libmp3lame", "-b:a", f"{options.bitrate_kbps}k"]
        else:
            args += ["-c:a", "pcm_s16le"]
        args += [safe_path(dest)]
        await _run_ffmpeg(ctx, args, dest=dest, duration=info.duration)
        return ToolOutput(
            file_path=dest, filename=name, mime_type=self.mime, resource_type=ResourceType.AUDIO
        )


# --------------------------------------------------------------------------
class ToMp4Options(BaseModel):
    model_config = {"extra": "forbid"}
    quality: Literal["high", "balanced", "small"] = "balanced"
    format: str = "best"


class VideoToMp4(Tool):
    spec = ToolSpec(
        id="video-to-mp4",
        category="video",
        capability=Capability.CONVERT,
        inputs=_URL_UPLOAD,
        accepts=_MEDIA,
        options_model=ToMp4Options,
        requires=frozenset({"ffmpeg"}),
        accepts_platform_media=True,
        order=14,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, ToMp4Options)
        info = await _probe(ctx, source)
        if not info.has_video:
            raise AppError(ErrorCode.FILE_TYPE_UNSUPPORTED, "This file has no video stream.")
        dest, name = output_name(ctx, stem_of(source), "mp4")
        video = info.video
        audio = info.audio
        notes: list[str] = []
        args = ["-i", safe_path(source.file.path), "-map", "0:v:0"]
        if audio:
            args += ["-map", "0:a:0"]
        remux = (
            video is not None
            and video.codec_name in {"h264"}
            and (audio is None or audio.codec_name in {"aac"})
            and options.quality == "balanced"
        )
        if remux:
            args += ["-c:v", "copy"]
            notes.append("remuxed_without_reencoding")
        else:
            crf = {"high": "18", "balanced": "23", "small": "28"}[options.quality]
            args += [
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                crf,
                "-pix_fmt",
                "yuv420p",
                "-vf",
                "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            ]
        if audio:
            args += ["-c:a", "copy"] if remux else ["-c:a", "aac", "-b:a", "160k"]
        args += ["-movflags", "+faststart", safe_path(dest)]
        await _run_ffmpeg(ctx, args, dest=dest, duration=info.duration)
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="video/mp4",
            resource_type=ResourceType.VIDEO,
            notes=notes,
        )


# --------------------------------------------------------------------------
class CompressOptions(BaseModel):
    model_config = {"extra": "forbid"}
    level: Literal["light", "medium", "strong"] = "medium"
    format: str = "best"


class VideoCompressor(Tool):
    spec = ToolSpec(
        id="video-compressor",
        category="video",
        capability=Capability.COMPRESS,
        inputs=_URL_UPLOAD,
        accepts=_MEDIA,
        options_model=CompressOptions,
        requires=frozenset({"ffmpeg"}),
        accepts_platform_media=True,
        order=15,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, CompressOptions)
        info = await _probe(ctx, source)
        if not info.has_video:
            raise AppError(ErrorCode.FILE_TYPE_UNSUPPORTED, "This file has no video stream.")
        crf, max_h, abr = {
            "light": ("26", 1080, "128k"),
            "medium": ("30", 720, "96k"),
            "strong": ("34", 480, "64k"),
        }[options.level]
        dest, name = output_name(ctx, f"{stem_of(source)}-compressed", "mp4")
        args = [
            "-i",
            safe_path(source.file.path),
            "-map",
            "0:v:0",
            *(["-map", "0:a:0"] if info.has_audio else []),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            crf,
            "-pix_fmt",
            "yuv420p",
            "-vf",
            f"scale=-2:'min({max_h},ih)'",
        ]
        if info.has_audio:
            args += ["-c:a", "aac", "-b:a", abr]
        args += ["-movflags", "+faststart", safe_path(dest)]
        await _run_ffmpeg(ctx, args, dest=dest, duration=info.duration)
        notes = []
        if dest.stat().st_size >= source.file.size_bytes:
            notes.append("output_not_smaller")
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="video/mp4",
            resource_type=ResourceType.VIDEO,
            notes=notes,
        )


# --------------------------------------------------------------------------
class GifOptions(BaseModel):
    model_config = {"extra": "forbid"}
    start_seconds: float = Field(default=0, ge=0, le=86400)
    duration_seconds: float = Field(default=5, gt=0, le=15)
    fps: int = Field(default=12, ge=1, le=30)
    width: int = Field(default=480, ge=32, le=1280)
    format: str = "best"


class VideoToGif(Tool):
    spec = ToolSpec(
        id="video-to-gif",
        category="video",
        capability=Capability.TO_GIF,
        inputs=_URL_UPLOAD,
        accepts=_MEDIA,
        options_model=GifOptions,
        requires=frozenset({"ffmpeg"}),
        accepts_platform_media=True,
        order=16,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, GifOptions)
        info = await _probe(ctx, source)
        if not info.has_video:
            raise AppError(ErrorCode.FILE_TYPE_UNSUPPORTED, "This file has no video stream.")
        if info.duration is not None and options.start_seconds >= info.duration:
            raise AppError(
                ErrorCode.INVALID_OPTIONS, "The start time is beyond the end of the video."
            )
        dest, name = output_name(ctx, stem_of(source), "gif")
        filters = (
            f"fps={options.fps},scale={options.width}:-2:flags=lanczos,"
            "split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5"
        )
        args = [
            "-ss",
            f"{options.start_seconds:.3f}",
            "-t",
            f"{options.duration_seconds:.3f}",
            "-i",
            safe_path(source.file.path),
            "-an",
            "-vf",
            filters,
            "-loop",
            "0",
            safe_path(dest),
        ]
        await _run_ffmpeg(ctx, args, dest=dest, duration=options.duration_seconds)
        return ToolOutput(
            file_path=dest, filename=name, mime_type="image/gif", resource_type=ResourceType.IMAGE
        )


# --------------------------------------------------------------------------
class ThumbnailOptions(BaseModel):
    model_config = {"extra": "forbid"}
    at_seconds: float | None = Field(
        default=None, ge=0, description="Timestamp; defaults to 10% into the video."
    )
    image_format: Literal["jpg", "png", "webp"] = "jpg"
    width: int | None = Field(default=None, ge=16, le=3840)
    format: str = Field(default="480p", description="Platform format used to fetch the video.")


class VideoThumbnail(Tool):
    spec = ToolSpec(
        id="video-thumbnail",
        category="video",
        capability=Capability.EXTRACT_THUMBNAIL,
        inputs=_URL_UPLOAD,
        accepts=_MEDIA,
        options_model=ThumbnailOptions,
        requires=frozenset({"ffmpeg"}),
        accepts_platform_media=True,
        platform_default_format="480p",
        order=17,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, ThumbnailOptions)
        info = await _probe(ctx, source)
        if not info.has_video:
            raise AppError(ErrorCode.FILE_TYPE_UNSUPPORTED, "This file has no video stream.")
        at = options.at_seconds
        if at is None:
            at = (info.duration or 0) * 0.1
        elif info.duration is not None and at > info.duration:
            raise AppError(
                ErrorCode.INVALID_OPTIONS, "The timestamp is beyond the end of the video."
            )
        mime = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}[options.image_format]
        dest, name = output_name(ctx, f"{stem_of(source)}-thumbnail", options.image_format)
        args = ["-ss", f"{at:.3f}", "-i", safe_path(source.file.path), "-frames:v", "1", "-an"]
        if options.width:
            args += ["-vf", f"scale={options.width}:-2"]
        if options.image_format == "jpg":
            args += ["-q:v", "2"]
        args += [safe_path(dest)]
        await _run_ffmpeg(ctx, args, dest=dest, duration=None)
        if not dest.exists():
            raise AppError(
                ErrorCode.PROCESSING_FAILED, "No frame could be extracted at that position."
            )
        return ToolOutput(
            file_path=dest, filename=name, mime_type=mime, resource_type=ResourceType.IMAGE
        )


# --------------------------------------------------------------------------
class VideoMetadata(Tool):
    spec = ToolSpec(
        id="video-metadata",
        category="video",
        capability=Capability.EXTRACT_METADATA,
        inputs=_URL_UPLOAD,
        accepts=_MEDIA,
        options_model=NoOptions,
        requires=frozenset({"ffmpeg"}),
        output="data",
        accepts_platform_media=True,
        order=18,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        info = await _probe(ctx, source)
        data = info.to_dict()
        data["filename"] = source.file.filename
        data["mime_type"] = source.file.mime_type
        data["size_bytes"] = source.file.size_bytes
        return ToolOutput(data=data, resource_type=ResourceType.VIDEO)


register(DownloadTool("video-downloader", "video", {ResourceType.VIDEO}, platform=True, order=10))
register(_VideoToAudio("video-to-mp3", "libmp3lame", "mp3", "audio/mpeg", 12))
register(_VideoToAudio("video-to-wav", "pcm_s16le", "wav", "audio/wav", 13))
register(VideoToMp4())
register(VideoCompressor())
register(VideoToGif())
register(VideoThumbnail())
register(VideoMetadata())
