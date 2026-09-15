"""Vimeo public videos."""

from __future__ import annotations

import re

from anything_download.domain import Platform
from anything_download.extractors.platforms.ytdlp_base import YtDlpExtractor
from anything_download.extractors.registry import register
from anything_download.security.urls import ParsedURL

_VIDEO_PATH = re.compile(r"^/(\d+|video/\d+|channels/[^/]+/\d+|groups/[^/]+/videos/\d+)(/|$)")


class VimeoExtractor(YtDlpExtractor):
    name = "vimeo"
    platform = Platform.VIMEO
    domains = ("vimeo.com", "player.vimeo.com")

    def matches_path(self, parsed: ParsedURL) -> bool:
        return bool(_VIDEO_PATH.match(parsed.path))

    def restrictions(self) -> list[str]:
        return ["public_content_only", "password_protected_unsupported"]


register(VimeoExtractor())
