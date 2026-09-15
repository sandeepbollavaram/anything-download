"""Reddit public video posts (v.redd.it hosted media)."""

from __future__ import annotations

import re

from anything_download.domain import Platform
from anything_download.extractors.platforms.ytdlp_base import YtDlpExtractor
from anything_download.extractors.registry import register
from anything_download.security.urls import ParsedURL

_POST_PATH = re.compile(r"^/(r/[^/]+/comments/|comments/|user/[^/]+/comments/|r/[^/]+/s/)")


class RedditExtractor(YtDlpExtractor):
    name = "reddit"
    platform = Platform.REDDIT
    domains = ("reddit.com", "redd.it", "v.redd.it")

    def matches_path(self, parsed: ParsedURL) -> bool:
        if parsed.host.endswith("redd.it"):
            return len(parsed.path.strip("/")) > 0
        return bool(_POST_PATH.match(parsed.path))

    def restrictions(self) -> list[str]:
        return ["public_content_only", "video_posts_only"]


register(RedditExtractor())
