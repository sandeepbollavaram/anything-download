"""Dailymotion public videos."""

from __future__ import annotations

from anything_download.domain import Platform
from anything_download.extractors.platforms.ytdlp_base import YtDlpExtractor
from anything_download.extractors.registry import register
from anything_download.security.urls import ParsedURL


class DailymotionExtractor(YtDlpExtractor):
    name = "dailymotion"
    platform = Platform.DAILYMOTION
    domains = ("dailymotion.com", "dai.ly")

    def matches_path(self, parsed: ParsedURL) -> bool:
        if parsed.host.endswith("dai.ly"):
            return len(parsed.path.strip("/")) > 0
        return parsed.path.startswith(("/video/", "/embed/video/"))

    def restrictions(self) -> list[str]:
        return ["public_content_only"]


register(DailymotionExtractor())
