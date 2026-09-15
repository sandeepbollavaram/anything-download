"""Instagram public posts and reels.

Instagram frequently requires a logged-in session even for public content.
When that happens the extractor reports ``SOURCE_REQUIRES_AUTH``; we never
supply cookies or credentials.
"""

from __future__ import annotations

import re

from anything_download.domain import Platform
from anything_download.extractors.platforms.ytdlp_base import YtDlpExtractor
from anything_download.extractors.registry import register
from anything_download.security.urls import ParsedURL

_POST_PATH = re.compile(r"^/(p|reel|reels|tv)/[A-Za-z0-9_-]+/?$")


class InstagramExtractor(YtDlpExtractor):
    name = "instagram"
    platform = Platform.INSTAGRAM
    domains = ("instagram.com",)

    def matches_path(self, parsed: ParsedURL) -> bool:
        return bool(_POST_PATH.match(parsed.path))

    def restrictions(self) -> list[str]:
        return ["public_content_only", "login_often_required", "stories_unsupported"]


register(InstagramExtractor())
