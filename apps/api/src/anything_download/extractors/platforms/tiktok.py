"""TikTok public videos."""

from __future__ import annotations

import re

from anything_download.domain import Platform
from anything_download.extractors.platforms.ytdlp_base import YtDlpExtractor
from anything_download.extractors.registry import register
from anything_download.security.urls import ParsedURL

_VIDEO_PATH = re.compile(r"^/(@[^/]+/video/\d+|v/\d+|t/[A-Za-z0-9]+|embed/)")


class TikTokExtractor(YtDlpExtractor):
    name = "tiktok"
    platform = Platform.TIKTOK
    domains = ("tiktok.com", "vm.tiktok.com", "vt.tiktok.com")

    def matches_path(self, parsed: ParsedURL) -> bool:
        if parsed.host in {"vm.tiktok.com", "vt.tiktok.com"}:
            return len(parsed.path.strip("/")) > 0
        return bool(_VIDEO_PATH.match(parsed.path))

    def restrictions(self) -> list[str]:
        return ["public_content_only", "extraction_may_be_blocked"]


register(TikTokExtractor())
