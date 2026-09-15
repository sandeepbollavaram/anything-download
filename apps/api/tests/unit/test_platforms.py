"""Platform extractor tests with deterministic yt-dlp fixtures (no network)."""

from typing import Any

import pytest

from anything_download.domain import Platform
from anything_download.errors import ErrorCode
from anything_download.extractors.platforms.ytdlp_base import (
    FORMAT_AUDIO,
    FORMAT_BEST,
    build_formats,
    map_ytdlp_error,
)
from anything_download.extractors.registry import all_extractors, find_extractor, get_extractor
from anything_download.security.urls import ValidatedURL, parse_url


def _fmt(**kw: Any) -> dict[str, Any]:
    base = {"url": "https://cdn/x", "vcodec": "avc1", "acodec": "none", "ext": "mp4", "tbr": 1000}
    base.update(kw)
    return base


INFO: dict[str, Any] = {
    "id": "abc123",
    "title": "Test video",
    "duration": 125,
    "thumbnail": "https://i.example/thumb.jpg",
    "webpage_url": "https://www.youtube.com/watch?v=abc123",
    "formats": [
        _fmt(format_id="1", height=1080, width=1920, fps=30, filesize=50_000_000),
        _fmt(format_id="2", height=720, width=1280, fps=30, filesize_approx=20_000_000),
        _fmt(format_id="3", height=360, width=640),
        _fmt(format_id="4", height=360, width=640, acodec="mp4a", tbr=500),
        _fmt(format_id="a1", vcodec="none", acodec="opus", ext="webm", abr=128, filesize=2_000_000),
        _fmt(format_id="a2", vcodec="none", acodec="mp4a", ext="m4a", abr=96),
    ],
}


def test_build_formats_ladder() -> None:
    formats, restrictions = build_formats(INFO)
    ids = [f.id for f in formats]
    assert ids == [FORMAT_BEST, "1080p", "720p", "360p", FORMAT_AUDIO]
    assert restrictions == []
    best = formats[0]
    assert best.height == 1080 and best.kind == "video+audio" and best.filesize == 50_000_000
    f720 = next(f for f in formats if f.id == "720p")
    assert f720.filesize_is_estimate is True
    audio = formats[-1]
    assert audio.kind == "audio" and audio.acodec == "opus" and audio.bitrate_kbps == 128


def test_build_formats_never_upscales() -> None:
    info = {**INFO, "formats": [_fmt(format_id="1", height=360, acodec="mp4a")]}
    formats, _ = build_formats(info)
    assert [f.id for f in formats] == [FORMAT_BEST, "360p", FORMAT_AUDIO]
    assert "1080p" not in [f.id for f in formats]


def test_build_formats_drm() -> None:
    info = {**INFO, "formats": [_fmt(format_id="1", height=720, has_drm=True)]}
    formats, restrictions = build_formats(info)
    assert formats == []
    assert "drm_protected" in restrictions


def test_build_analysis_ok() -> None:
    ext = get_extractor(Platform.YOUTUBE)
    assert ext is not None
    url = _validated("https://www.youtube.com/watch?v=abc123")
    analysis = ext.build_analysis(url, INFO)
    assert analysis.status == "ok"
    assert analysis.platform == Platform.YOUTUBE
    assert analysis.title == "Test video"
    assert analysis.duration_seconds == 125
    assert analysis.thumbnail == "https://i.example/thumb.jpg"
    assert [f.id for f in analysis.formats][:2] == [FORMAT_BEST, "1080p"]
    assert "public_content_only" in analysis.restrictions


def test_build_analysis_live_restricted() -> None:
    ext = get_extractor(Platform.YOUTUBE)
    assert ext is not None
    analysis = ext.build_analysis(
        _validated("https://www.youtube.com/watch?v=live"), {**INFO, "is_live": True}
    )
    assert analysis.status == "restricted"
    assert analysis.reason is not None and analysis.reason.code == ErrorCode.SOURCE_LIVE_STREAM
    assert analysis.formats == []


def test_build_analysis_private() -> None:
    ext = get_extractor(Platform.YOUTUBE)
    assert ext is not None
    analysis = ext.build_analysis(
        _validated("https://www.youtube.com/watch?v=p"), {**INFO, "availability": "needs_auth"}
    )
    assert analysis.status == "restricted"
    assert analysis.reason is not None and analysis.reason.code == ErrorCode.SOURCE_REQUIRES_AUTH


@pytest.mark.parametrize(
    ("message", "code"),
    [
        ("ERROR: [youtube] x: Sign in to confirm you're not a bot", ErrorCode.SOURCE_UNREACHABLE),
        ("ERROR: Sign in to view this video", ErrorCode.SOURCE_REQUIRES_AUTH),
        ("ERROR: This video is private", ErrorCode.SOURCE_PRIVATE),
        ("ERROR: This video is DRM protected", ErrorCode.SOURCE_DRM_PROTECTED),
        (
            "ERROR: The uploader has not made this video available in your country",
            ErrorCode.SOURCE_GEO_RESTRICTED,
        ),
        ("ERROR: This live event will begin in 3 hours", ErrorCode.SOURCE_LIVE_STREAM),
        ("ERROR: Requested format is not available", ErrorCode.FORMAT_UNAVAILABLE),
        ("ERROR: Unsupported URL: https://x", ErrorCode.SOURCE_UNSUPPORTED),
        ("ERROR: Video unavailable", ErrorCode.SOURCE_NOT_FOUND),
        ("ERROR: HTTP Error 429: Too Many Requests", ErrorCode.SOURCE_UNREACHABLE),
        ("ERROR: HTTP Error 403: Forbidden", ErrorCode.SOURCE_FORBIDDEN),
        (
            "ERROR: Join this channel to get access to members-only content",
            ErrorCode.SOURCE_REQUIRES_AUTH,
        ),
        (
            "ERROR: You have requested merging of multiple formats but ffmpeg is not installed.",
            ErrorCode.PROCESSING_FAILED,
        ),
        ("ERROR: something entirely new", ErrorCode.SOURCE_UNSUPPORTED),
    ],
)
def test_error_mapping(message: str, code: ErrorCode) -> None:
    assert map_ytdlp_error(message).code == code


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", Platform.YOUTUBE),
        ("https://youtu.be/dQw4w9WgXcQ", Platform.YOUTUBE),
        ("https://www.youtube.com/shorts/abc", Platform.YOUTUBE),
        ("https://vimeo.com/123456", Platform.VIMEO),
        ("https://player.vimeo.com/video/123456", Platform.VIMEO),
        ("https://www.dailymotion.com/video/x8abc", Platform.DAILYMOTION),
        ("https://dai.ly/x8abc", Platform.DAILYMOTION),
        ("https://www.reddit.com/r/videos/comments/abc/title/", Platform.REDDIT),
        ("https://v.redd.it/abc123", Platform.REDDIT),
        ("https://www.tiktok.com/@user/video/7000000000000000000", Platform.TIKTOK),
        ("https://vm.tiktok.com/ZMabc/", Platform.TIKTOK),
        ("https://www.twitch.tv/videos/123456", Platform.TWITCH),
        ("https://clips.twitch.tv/SomeClip", Platform.TWITCH),
        ("https://www.twitch.tv/streamer/clip/SomeClip", Platform.TWITCH),
        ("https://www.instagram.com/p/Cabc123/", Platform.INSTAGRAM),
        ("https://www.instagram.com/reel/Cabc123/", Platform.INSTAGRAM),
        ("https://www.facebook.com/watch/?v=123", Platform.FACEBOOK),
        ("https://fb.watch/abc/", Platform.FACEBOOK),
        ("https://www.facebook.com/somepage/videos/123/", Platform.FACEBOOK),
    ],
)
def test_detect(url: str, platform: Platform) -> None:
    ext = find_extractor(parse_url(url))
    assert ext is not None and ext.platform == platform


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/@channel",
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/results?search_query=x",
        "https://www.twitch.tv/somechannel",  # live channel page
        "https://www.instagram.com/someuser/",
        "https://www.instagram.com/stories/user/123/",
        "https://vimeo.com/",
        "https://example.com/watch?v=1",
        "https://notyoutube.com/watch?v=1",
    ],
)
def test_no_detect(url: str) -> None:
    assert find_extractor(parse_url(url)) is None


def test_all_platforms_registered() -> None:
    assert {e.platform for e in all_extractors()} == set(Platform)


def test_disabled_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from anything_download import config

    monkeypatch.setenv("AD_ENABLE_PLATFORM_EXTRACTORS", "false")
    config.reset_settings_cache()
    assert find_extractor(parse_url("https://youtu.be/abc")) is None


def _validated(url: str) -> ValidatedURL:
    p = parse_url(url)
    return ValidatedURL(
        url=p.url,
        scheme=p.scheme,
        host=p.host,
        port=p.port,
        path=p.path,
        query=p.query,
        is_ip_literal=False,
        resolved_ips=("93.184.216.34",),
    )


def test_ffmpeg_location_is_a_resolved_path(settings, monkeypatch) -> None:
    """yt-dlp treats ffmpeg_location as a path: a bare "ffmpeg" disabled every merge."""
    from anything_download.extractors.platforms import ytdlp_base

    monkeypatch.setattr(ytdlp_base.shutil, "which", lambda name: f"/usr/bin/{name}")
    assert ytdlp_base._base_opts(settings)["ffmpeg_location"] == "/usr/bin/ffmpeg"


def test_ffmpeg_location_omitted_when_ffmpeg_is_missing(settings, monkeypatch) -> None:
    from anything_download.extractors.platforms import ytdlp_base

    monkeypatch.setattr(ytdlp_base.shutil, "which", lambda name: None)
    assert "ffmpeg_location" not in ytdlp_base._base_opts(settings)
