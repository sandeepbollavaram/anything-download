"""Shared yt-dlp integration for platform extractors.

Policy:

* no cookies, no browser cookie import, no credentials; public content only
* no geo-bypass header spoofing
* DRM-protected, private, members-only, login-walled and live content is
  reported as restricted with a typed error instead of being circumvented
* only formats the source really exposes are offered; nothing is upscaled
"""

from __future__ import annotations

import asyncio
import re
import shutil
import threading
import time
from collections.abc import Awaitable
from pathlib import Path
from typing import Any

from anything_download.analysis.models import MediaFormat, URLAnalysis
from anything_download.config import Settings
from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.extractors.base import CancelFn, PlatformExtractor, ProgressFn
from anything_download.logging import get_logger
from anything_download.security.urls import ValidatedURL

log = get_logger(__name__)

_QUALITY_LADDER = (2160, 1440, 1080, 720, 480, 360, 240, 144)

FORMAT_BEST = "best"
FORMAT_AUDIO = "audio"


class _SilentLogger:
    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        log.debug("yt_dlp.warning", message=msg[:300])

    def error(self, msg: str) -> None:
        log.debug("yt_dlp.error", message=msg[:300])


class _AbortedError(Exception):
    pass


def _base_opts(settings: Settings) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "playlist_items": "1",
        "logger": _SilentLogger(),
        "socket_timeout": 20,
        "retries": 1,
        "fragment_retries": 2,
        "geo_bypass": False,
        "cookiefile": None,
        "cookiesfrombrowser": None,
        "usenetrc": False,
        "username": None,
        "password": None,
        "nocheckcertificate": False,
        "age_limit": None,
        "ignoreerrors": False,
        "noprogress": True,
        "cachedir": False,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "http_headers": {"User-Agent": settings.user_agent},
    }
    # yt-dlp treats ffmpeg_location as a filesystem path. The setting is usually a bare
    # command name ("ffmpeg"), which yt-dlp then reported as missing, disabling merges:
    # every video+audio download failed. Resolve it; if it cannot be found, let yt-dlp
    # search PATH itself.
    ffmpeg = shutil.which(settings.ffmpeg_bin)
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    return opts


def map_ytdlp_error(message: str) -> AppError:
    """Translate yt-dlp error text into a typed, user-facing error."""
    text = message.lower()
    if "drm" in text or "widevine" in text or "fairplay" in text:
        return AppError(
            ErrorCode.SOURCE_DRM_PROTECTED, "This content is DRM protected and cannot be processed."
        )
    if "private video" in text or "this video is private" in text or "private account" in text:
        return AppError(
            ErrorCode.SOURCE_PRIVATE,
            "This content is private and cannot be accessed without permission.",
        )
    # YouTube's anti-bot check reads "Sign in to confirm you're not a bot". It throttles
    # this server's IP, not the video, so it must not be reported as a login wall.
    if "not a bot" in text:
        return AppError(
            ErrorCode.SOURCE_UNREACHABLE,
            "The platform is temporarily limiting requests from this server. "
            "Please try again later.",
            retryable=True,
        )
    if any(
        k in text
        for k in (
            "sign in",
            "log in",
            "login required",
            "logged in",
            "login to",
            "requires authentication",
            "members-only",
            "members only",
            "subscriber",
            "premium",
            "purchase",
            "rate-limit reached or login",
        )
    ):
        return AppError(
            ErrorCode.SOURCE_REQUIRES_AUTH,
            "This content requires signing in to the platform, which is not supported.",
        )
    if (
        "in your country" in text
        or ("geo" in text and "restrict" in text)
        or "not available in your region" in text
    ):
        return AppError(
            ErrorCode.SOURCE_GEO_RESTRICTED,
            "This content is not available from the server's region.",
        )
    if "live" in text and ("event" in text or "stream" in text or "premiere" in text):
        return AppError(
            ErrorCode.SOURCE_LIVE_STREAM, "Live streams and premieres are not supported."
        )
    if "requested format is not available" in text or "no video formats" in text:
        return AppError(
            ErrorCode.FORMAT_UNAVAILABLE, "The requested quality is not available for this source."
        )
    if "unsupported url" in text:
        return AppError(
            ErrorCode.SOURCE_UNSUPPORTED, "This URL is not a supported media page on the platform."
        )
    if (
        "http error 404" in text
        or "video unavailable" in text
        or "has been removed" in text
        or "does not exist" in text
        or "not found" in text
    ):
        return AppError(
            ErrorCode.SOURCE_NOT_FOUND, "The content could not be found. It may have been removed."
        )
    if "http error 429" in text or "too many requests" in text:
        return AppError(
            ErrorCode.SOURCE_UNREACHABLE,
            "The platform is rate limiting requests. Please try again later.",
            retryable=True,
        )
    if "http error 403" in text or "forbidden" in text:
        return AppError(ErrorCode.SOURCE_FORBIDDEN, "The platform refused access to this content.")
    if "timed out" in text or "timeout" in text:
        return AppError(ErrorCode.SOURCE_TIMEOUT, "The platform took too long to respond.")
    if "ffmpeg is not installed" in text or "ffmpeg-location" in text:
        return AppError(
            ErrorCode.PROCESSING_FAILED,
            "This format needs FFmpeg to combine video and audio, and it is not available on "
            "this server.",
        )
    if "file is larger than max-filesize" in text or "max_filesize" in text:
        return AppError(
            ErrorCode.SOURCE_TOO_LARGE, "The selected format exceeds the maximum file size limit."
        )
    # Unrecognised: keep the text in the log (URLs in `message` are redacted) so a
    # local failure is not silently reported to users as a platform block.
    log.warning("ytdlp.unmapped_error", message=message[:500])
    return AppError(
        ErrorCode.SOURCE_UNSUPPORTED,
        "This source is currently unsupported. The platform may have changed or blocked extraction.",
    )


def _selector_for(format_id: str) -> str:
    if format_id == FORMAT_BEST:
        return "bestvideo*+bestaudio/best"
    if format_id == FORMAT_AUDIO:
        return "bestaudio/best"
    m = re.fullmatch(r"(\d{3,4})p", format_id)
    if m:
        h = int(m.group(1))
        return f"bestvideo*[height<={h}]+bestaudio/best[height<={h}]/best"
    raise AppError(ErrorCode.FORMAT_UNAVAILABLE, f"Unknown format '{format_id}'.")


def build_formats(info: dict[str, Any]) -> tuple[list[MediaFormat], list[str]]:
    """Derive the user-facing quality ladder from yt-dlp's format list."""
    restrictions: list[str] = []
    raw_formats: list[dict[str, Any]] = [
        f for f in (info.get("formats") or []) if isinstance(f, dict)
    ]
    usable = [f for f in raw_formats if not f.get("has_drm") and f.get("url")]
    if raw_formats and not usable:
        restrictions.append("drm_protected")
        return [], restrictions

    video = [f for f in usable if (f.get("vcodec") or "none") != "none" and f.get("height")]
    audio = [
        f
        for f in usable
        if (f.get("acodec") or "none") != "none" and (f.get("vcodec") or "none") == "none"
    ]
    has_audio_anywhere = bool(audio) or any((f.get("acodec") or "none") != "none" for f in usable)
    formats: list[MediaFormat] = []
    if video:
        best = max(video, key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
        formats.append(
            MediaFormat(
                id=FORMAT_BEST,
                label=f"Best available ({best.get('height')}p)",
                kind="video+audio" if has_audio_anywhere else "video",
                ext=best.get("ext"),
                width=best.get("width"),
                height=best.get("height"),
                fps=best.get("fps"),
                filesize=best.get("filesize") or best.get("filesize_approx"),
                filesize_is_estimate=not best.get("filesize"),
                vcodec=best.get("vcodec"),
                acodec=best.get("acodec") if (best.get("acodec") or "none") != "none" else None,
            )
        )
        for h in _QUALITY_LADDER:
            candidates = [f for f in video if int(f["height"]) == h]
            if not candidates:
                continue
            pick = max(candidates, key=lambda f: f.get("tbr") or 0)
            formats.append(
                MediaFormat(
                    id=f"{h}p",
                    label=f"{h}p",
                    kind="video+audio" if has_audio_anywhere else "video",
                    ext=pick.get("ext"),
                    width=pick.get("width"),
                    height=h,
                    fps=pick.get("fps"),
                    filesize=pick.get("filesize") or pick.get("filesize_approx"),
                    filesize_is_estimate=not pick.get("filesize"),
                    vcodec=pick.get("vcodec"),
                )
            )
    if has_audio_anywhere:
        best_audio: dict[str, Any] | None = (
            max(audio, key=lambda f: f.get("abr") or f.get("tbr") or 0) if audio else None
        )
        formats.append(
            MediaFormat(
                id=FORMAT_AUDIO,
                label="Audio only",
                kind="audio",
                ext=best_audio.get("ext") if best_audio else None,
                filesize=(best_audio.get("filesize") or best_audio.get("filesize_approx"))
                if best_audio
                else None,
                filesize_is_estimate=bool(best_audio and not best_audio.get("filesize")),
                acodec=best_audio.get("acodec") if best_audio else None,
                bitrate_kbps=(best_audio.get("abr") or best_audio.get("tbr"))
                if best_audio
                else None,
            )
        )
    return formats, restrictions


class YtDlpExtractor(PlatformExtractor):
    """Platform extractor backed by yt-dlp. Subclasses set ``domains``/``platform``."""

    analyze_timeout: float = 45.0
    supports_audio_only: bool = True

    async def analyze(self, url: ValidatedURL, settings: Settings) -> URLAnalysis:
        import yt_dlp

        opts = {**_base_opts(settings), "skip_download": True, "extract_flat": False}

        def _run() -> dict[str, Any]:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url.url, download=False)
            if not isinstance(info, dict):
                raise AppError(
                    ErrorCode.SOURCE_UNSUPPORTED, "The platform returned no media information."
                )
            if info.get("_type") == "playlist":
                entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
                if not entries:
                    raise AppError(
                        ErrorCode.SOURCE_UNSUPPORTED,
                        "This link is a playlist or channel without directly processable media.",
                    )
                info = entries[0]
            return info

        try:
            info = await asyncio.wait_for(asyncio.to_thread(_run), timeout=self.analyze_timeout)
        except TimeoutError as exc:
            raise AppError(
                ErrorCode.SOURCE_TIMEOUT, "The platform took too long to respond."
            ) from exc
        except AppError:
            raise
        except yt_dlp.utils.DownloadError as exc:
            raise map_ytdlp_error(str(exc)) from exc
        except yt_dlp.utils.YoutubeDLError as exc:
            raise map_ytdlp_error(str(exc)) from exc
        except Exception as exc:
            log.warning(
                "ytdlp.analyze_failed", platform=self.platform.value, error=type(exc).__name__
            )
            raise map_ytdlp_error(str(exc)) from exc
        return self.build_analysis(url, info)

    def build_analysis(self, url: ValidatedURL, info: dict[str, Any]) -> URLAnalysis:
        formats, restrictions = build_formats(info)
        restrictions.extend(self.restrictions())
        warnings: list[str] = []
        status: str = "ok"
        reason: AppError | None = None
        if info.get("is_live") or info.get("live_status") in {
            "is_live",
            "is_upcoming",
            "post_live",
        }:
            restrictions.append("live_stream")
            reason = AppError(
                ErrorCode.SOURCE_LIVE_STREAM,
                "Live streams are not supported. Try again after the recording is published.",
            )
        elif "drm_protected" in restrictions:
            reason = AppError(
                ErrorCode.SOURCE_DRM_PROTECTED,
                "This content is DRM protected and cannot be processed.",
            )
        elif info.get("availability") in {
            "private",
            "premium_only",
            "subscriber_only",
            "needs_auth",
        }:
            restrictions.append(str(info.get("availability")))
            reason = AppError(
                ErrorCode.SOURCE_REQUIRES_AUTH, "This content is not publicly available."
            )
        elif not formats:
            reason = AppError(
                ErrorCode.FORMAT_UNAVAILABLE,
                "The platform did not expose any downloadable formats for this content.",
            )
        if reason is not None:
            status = "restricted" if reason.code != ErrorCode.FORMAT_UNAVAILABLE else "unsupported"

        has_video = any(f.kind != "audio" for f in formats)
        resource_type = ResourceType.VIDEO if has_video or not formats else ResourceType.AUDIO
        thumbnail = info.get("thumbnail")
        if not thumbnail and isinstance(info.get("thumbnails"), list) and info["thumbnails"]:
            last = info["thumbnails"][-1]
            thumbnail = last.get("url") if isinstance(last, dict) else None
        if info.get("age_limit") and int(info.get("age_limit") or 0) >= 18:
            warnings.append("age_restricted")

        best = next((f for f in formats if f.id == FORMAT_BEST), None)
        return URLAnalysis(
            normalized_url=url.url,
            final_url=info.get("webpage_url") if info.get("webpage_url") != url.url else None,
            source_kind="platform",
            resource_type=resource_type,
            platform=self.platform,
            mime_type=None,
            title=_clip(info.get("title")),
            description=_clip(info.get("description"), 600),
            thumbnail=thumbnail
            if isinstance(thumbnail, str) and thumbnail.startswith("http")
            else None,
            duration_seconds=float(info["duration"])
            if isinstance(info.get("duration"), int | float)
            else None,
            size_bytes=best.filesize if best else None,
            width=best.width if best else None,
            height=best.height if best else None,
            formats=formats if status == "ok" else [],
            restrictions=sorted(set(restrictions)),
            warnings=warnings,
            capabilities=[Capability.DOWNLOAD] if status == "ok" else [],
            tools=[],
            status=status,  # type: ignore[arg-type]
            reason=reason.to_payload() if reason else None,
        )

    async def download(
        self,
        url: ValidatedURL,
        *,
        format_id: str,
        dest_dir: Path,
        settings: Settings,
        progress: ProgressFn,
        is_cancelled: CancelFn,
        max_bytes: int,
        timeout: float,
    ) -> Path:
        import yt_dlp

        selector = _selector_for(format_id)
        loop = asyncio.get_running_loop()
        abort = threading.Event()
        last_report = [0.0]

        def hook(d: dict[str, Any]) -> None:
            if abort.is_set():
                raise _AbortedError()
            now = time.monotonic()
            if now - last_report[0] < 1.0:
                return
            last_report[0] = now
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                done = d.get("downloaded_bytes")
                pct = (done / total * 100.0) if total and done is not None else None
                asyncio.run_coroutine_threadsafe(_await(progress("downloading", pct, None)), loop)
            elif status == "finished":
                asyncio.run_coroutine_threadsafe(_await(progress("processing", None, None)), loop)

        opts = {
            **_base_opts(settings),
            "format": selector,
            "outtmpl": {"default": str(dest_dir / "%(id)s.%(ext)s")},
            "max_filesize": max_bytes,
            "progress_hooks": [hook],
            "merge_output_format": "mp4",
            "overwrites": True,
            "concurrent_fragment_downloads": 1,
            "paths": {"home": str(dest_dir), "temp": str(dest_dir)},
        }
        if format_id == FORMAT_AUDIO:
            opts.pop("merge_output_format", None)

        def _run() -> Path:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url.url, download=True)
                if not isinstance(info, dict):
                    raise AppError(ErrorCode.SOURCE_UNSUPPORTED, "The platform returned no media.")
                if info.get("_type") == "playlist":
                    entries = [e for e in (info.get("entries") or []) if isinstance(e, dict)]
                    info = entries[0] if entries else info
                downloads = info.get("requested_downloads") or []
                path_str = None
                if downloads and isinstance(downloads[0], dict):
                    path_str = downloads[0].get("filepath")
                if not path_str:
                    path_str = ydl.prepare_filename(info)
                path = Path(path_str)
                if not path.exists():
                    candidates = [
                        p
                        for p in dest_dir.iterdir()
                        if p.is_file() and not p.name.endswith((".part", ".ytdl"))
                    ]
                    if not candidates:
                        raise AppError(
                            ErrorCode.PROCESSING_FAILED,
                            "The download finished but no file was produced.",
                        )
                    path = max(candidates, key=lambda p: p.stat().st_size)
                return path

        async def watch_cancel() -> None:
            while not abort.is_set():
                await asyncio.sleep(1.0)
                if await is_cancelled():
                    abort.set()
                    return

        watcher = asyncio.create_task(watch_cancel())
        try:
            path = await asyncio.wait_for(asyncio.to_thread(_run), timeout=timeout)
        except TimeoutError as exc:
            abort.set()
            raise AppError(
                ErrorCode.PROCESSING_TIMEOUT, "Downloading from the platform took too long."
            ) from exc
        except _AbortedError:
            from anything_download.tools.base import JobCancelled

            raise JobCancelled() from None
        except AppError:
            raise
        except yt_dlp.utils.YoutubeDLError as exc:
            if abort.is_set():
                from anything_download.tools.base import JobCancelled

                raise JobCancelled() from None
            raise map_ytdlp_error(str(exc)) from exc
        except Exception as exc:
            if abort.is_set():
                from anything_download.tools.base import JobCancelled

                raise JobCancelled() from None
            log.warning(
                "ytdlp.download_failed", platform=self.platform.value, error=type(exc).__name__
            )
            raise map_ytdlp_error(str(exc)) from exc
        finally:
            abort.set()
            watcher.cancel()
        if path.stat().st_size > max_bytes:
            path.unlink(missing_ok=True)
            raise AppError(
                ErrorCode.SOURCE_TOO_LARGE,
                "The downloaded media exceeds the maximum file size limit.",
            )
        return path


async def _await(aw: Awaitable[None]) -> None:
    await aw


def _clip(value: Any, limit: int = 300) -> str | None:
    if not isinstance(value, str):
        return None
    text = re.sub(r"\s+", " ", value).strip()
    return text[:limit] or None


__all__ = [
    "FORMAT_AUDIO",
    "FORMAT_BEST",
    "YtDlpExtractor",
    "build_formats",
    "map_ytdlp_error",
]
