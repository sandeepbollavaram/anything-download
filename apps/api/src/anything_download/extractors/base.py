"""Extractor plugin interface.

Extractors turn a validated URL into a :class:`URLAnalysis` and, for platform
sources, download a chosen format into a local file. Three families exist:

* :mod:`direct`          - a URL that points straight at a file
* :mod:`generic_webpage` - an ordinary HTML page with referenced resources
* :mod:`platforms.*`     - supported public media platforms (via yt-dlp)
"""

from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from pathlib import Path

from anything_download.analysis.models import URLAnalysis
from anything_download.config import Settings
from anything_download.domain import Platform
from anything_download.security.urls import ParsedURL, ValidatedURL

ProgressFn = Callable[[str, float | None, str | None], Awaitable[None]]
CancelFn = Callable[[], Awaitable[bool]]


class PlatformExtractor(abc.ABC):
    """Base class for third-party platform extractors."""

    name: str
    platform: Platform
    #: Registered hostnames (exact or suffix match, without leading dot).
    domains: tuple[str, ...] = ()

    def detect(self, parsed: ParsedURL) -> bool:
        host = parsed.host.lower()
        for d in self.domains:
            if host == d or host.endswith("." + d):
                return self.matches_path(parsed)
        return False

    def matches_path(self, parsed: ParsedURL) -> bool:
        """Refine detection by path (e.g. only /watch or /shorts URLs)."""
        return True

    @abc.abstractmethod
    async def analyze(self, url: ValidatedURL, settings: Settings) -> URLAnalysis: ...

    @abc.abstractmethod
    async def download(
        self,
        url: ValidatedURL,
        *,
        format_id: str,
        dest_dir: Path,
        settings: Settings,
        progress: ProgressFn,
        is_cancelled: CancelFn,
        max_bytes: int,
        timeout: float,
    ) -> Path:
        """Download ``format_id`` into ``dest_dir`` and return the file path."""

    def restrictions(self) -> list[str]:
        """Static restriction codes shown for every URL on this platform."""
        return []
