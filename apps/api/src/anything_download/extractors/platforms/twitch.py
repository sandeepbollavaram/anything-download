"""Twitch clips and published VODs (live channels are not supported)."""

from __future__ import annotations

import re

from anything_download.domain import Platform
from anything_download.extractors.platforms.ytdlp_base import YtDlpExtractor
from anything_download.extractors.registry import register
from anything_download.security.urls import ParsedURL

_ALLOWED = re.compile(r"^/(videos/\d+|[^/]+/clip/[^/]+|clip/[^/]+)(/|$)")


class TwitchExtractor(YtDlpExtractor):
    name = "twitch"
    platform = Platform.TWITCH
    domains = ("twitch.tv", "clips.twitch.tv", "m.twitch.tv")

    def matches_path(self, parsed: ParsedURL) -> bool:
        if parsed.host == "clips.twitch.tv":
            return len(parsed.path.strip("/")) > 0
        # Channel pages (/{channel}) are live streams: deliberately not matched.
        return bool(_ALLOWED.match(parsed.path))

    def restrictions(self) -> list[str]:
        return ["public_content_only", "live_streams_unsupported", "subscriber_only_unsupported"]


register(TwitchExtractor())
