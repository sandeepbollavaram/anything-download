"""YouTube public videos and Shorts."""

from __future__ import annotations

import re

from anything_download.domain import Platform
from anything_download.extractors.platforms.ytdlp_base import YtDlpExtractor
from anything_download.extractors.registry import register
from anything_download.security.urls import ParsedURL

_WATCH_PATHS = re.compile(r"^/(watch|shorts/|embed/|v/|live/)")


class YouTubeExtractor(YtDlpExtractor):
    name = "youtube"
    platform = Platform.YOUTUBE
    domains = (
        "youtube.com",
        "youtu.be",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
    )

    def matches_path(self, parsed: ParsedURL) -> bool:
        if parsed.host.endswith("youtu.be"):
            return len(parsed.path.strip("/")) > 0
        if parsed.path.startswith(
            ("/playlist", "/channel", "/@", "/c/", "/user/", "/results", "/feed")
        ):
            return False
        return bool(_WATCH_PATHS.match(parsed.path))

    def restrictions(self) -> list[str]:
        return ["public_content_only"]


register(YouTubeExtractor())
