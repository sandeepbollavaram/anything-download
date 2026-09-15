"""Registry of platform extractors."""

from __future__ import annotations

import importlib

from anything_download.config import Settings, get_settings
from anything_download.domain import Platform
from anything_download.extractors.base import PlatformExtractor
from anything_download.security.urls import ParsedURL

_EXTRACTORS: list[PlatformExtractor] = []
_LOADED = False

_PLATFORM_MODULES = (
    "anything_download.extractors.platforms.youtube",
    "anything_download.extractors.platforms.vimeo",
    "anything_download.extractors.platforms.dailymotion",
    "anything_download.extractors.platforms.reddit",
    "anything_download.extractors.platforms.tiktok",
    "anything_download.extractors.platforms.twitch",
    "anything_download.extractors.platforms.instagram",
    "anything_download.extractors.platforms.facebook",
)


def register(extractor: PlatformExtractor) -> PlatformExtractor:
    _EXTRACTORS.append(extractor)
    return extractor


def load_all() -> None:
    global _LOADED  # noqa: PLW0603
    if _LOADED:
        return
    for module in _PLATFORM_MODULES:
        importlib.import_module(module)
    _LOADED = True


def all_extractors() -> list[PlatformExtractor]:
    load_all()
    return list(_EXTRACTORS)


def find_extractor(parsed: ParsedURL, settings: Settings | None = None) -> PlatformExtractor | None:
    settings = settings or get_settings()
    if not settings.enable_platform_extractors:
        return None
    for extractor in all_extractors():
        if extractor.detect(parsed):
            return extractor
    return None


def get_extractor(platform: Platform) -> PlatformExtractor | None:
    return next((e for e in all_extractors() if e.platform == platform), None)
