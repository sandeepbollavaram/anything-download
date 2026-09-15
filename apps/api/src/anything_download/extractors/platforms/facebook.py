"""Facebook public videos and reels.

Only content that is visible without logging in can be processed. Group,
friends-only and login-walled videos yield ``SOURCE_REQUIRES_AUTH``.
"""

from __future__ import annotations

import re

from anything_download.domain import Platform
from anything_download.extractors.platforms.ytdlp_base import YtDlpExtractor
from anything_download.extractors.registry import register
from anything_download.security.urls import ParsedURL

_VIDEO_PATH = re.compile(
    r"^/([^/]+/videos/|watch/?$|watch/|reel/|video\.php|share/[rv]/|[^/]+/posts/)"
)


class FacebookExtractor(YtDlpExtractor):
    name = "facebook"
    platform = Platform.FACEBOOK
    domains = ("facebook.com", "fb.watch", "m.facebook.com", "web.facebook.com", "fb.com")

    def matches_path(self, parsed: ParsedURL) -> bool:
        if parsed.host.endswith("fb.watch"):
            return len(parsed.path.strip("/")) > 0
        if parsed.path.startswith("/watch") and "v=" in parsed.query:
            return True
        return bool(_VIDEO_PATH.match(parsed.path))

    def restrictions(self) -> list[str]:
        return ["public_content_only", "login_often_required"]


register(FacebookExtractor())
