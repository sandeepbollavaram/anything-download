"""Platform extractor host matching.

yt-dlp does its own DNS resolution and connection, outside SafeHttpClient's
IP pinning. What keeps that from being a general SSRF primitive is that yt-dlp
is only ever reached for a host on a registered extractor's fixed allowlist --
there is no generic/wildcard fallback. These tests pin that property down, so
a loosened matcher (substring instead of suffix, say) fails loudly.
"""

from __future__ import annotations

import pytest

from anything_download.config import Settings
from anything_download.extractors.registry import find_extractor
from anything_download.security.urls import parse_url


def _match(raw: str, settings: Settings) -> str | None:
    extractor = find_extractor(parse_url(raw, settings), settings)
    return extractor.name if extractor else None


@pytest.mark.security
@pytest.mark.parametrize(
    "raw",
    [
        # Look-alikes that must never reach a platform extractor.
        "https://youtube.com.evil.example/watch?v=abc",
        "https://notyoutube.com/watch?v=abc",
        "https://evil-youtube.com/watch?v=abc",
        "https://youtube.com.attacker.net/watch?v=abc",
        "https://fakevimeo.com/12345",
        "https://vimeo.com.evil.example/12345",
        "https://tiktok.com.evil.example/@x/video/1",
        "https://reddit.com.evil.example/r/x/comments/y/z/",
        # Unrelated hosts.
        "https://example.com/watch?v=abc",
        "https://cdn.example.org/video.mp4",
    ],
)
def test_lookalike_hosts_do_not_reach_ytdlp(raw: str, settings: Settings) -> None:
    assert _match(raw, settings) is None


@pytest.mark.security
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://m.youtube.com/watch?v=dQw4w9WgXcQ", "youtube"),
        ("https://youtu.be/dQw4w9WgXcQ", "youtube"),
        ("https://vimeo.com/123456789", "vimeo"),
    ],
)
def test_genuine_platform_hosts_still_match(raw: str, expected: str, settings: Settings) -> None:
    assert _match(raw, settings) == expected


@pytest.mark.security
def test_platform_extraction_can_be_disabled(settings: Settings) -> None:
    disabled = settings.model_copy(update={"enable_platform_extractors": False})

    assert _match("https://www.youtube.com/watch?v=dQw4w9WgXcQ", disabled) is None


@pytest.mark.security
def test_non_media_youtube_paths_are_not_extracted(settings: Settings) -> None:
    """Channel/playlist/search pages are not processable media and must not be fetched."""
    for path in ("/playlist?list=x", "/channel/UC123", "/@someone", "/results?search_query=x"):
        assert _match(f"https://www.youtube.com{path}", settings) is None
