"""Core domain enums shared across the analysis engine, tools and API."""

from __future__ import annotations

from enum import StrEnum


class ResourceType(StrEnum):
    VIDEO = "VIDEO"
    IMAGE = "IMAGE"
    AUDIO = "AUDIO"
    PDF = "PDF"
    DOCUMENT = "DOCUMENT"
    WEBPAGE = "WEBPAGE"
    ARCHIVE = "ARCHIVE"
    UNKNOWN = "UNKNOWN"


class Capability(StrEnum):
    DOWNLOAD = "DOWNLOAD"
    CONVERT = "CONVERT"
    COMPRESS = "COMPRESS"
    RESIZE = "RESIZE"
    EXTRACT_AUDIO = "EXTRACT_AUDIO"
    EXTRACT_THUMBNAIL = "EXTRACT_THUMBNAIL"
    EXTRACT_METADATA = "EXTRACT_METADATA"
    CONVERT_TO_PDF = "CONVERT_TO_PDF"
    PDF_TO_IMAGES = "PDF_TO_IMAGES"
    PDF_TO_TEXT = "PDF_TO_TEXT"
    MERGE = "MERGE"
    SPLIT = "SPLIT"
    TO_GIF = "TO_GIF"
    FIND_IMAGES = "FIND_IMAGES"
    FIND_VIDEOS = "FIND_VIDEOS"
    FIND_AUDIO = "FIND_AUDIO"
    FIND_PDFS = "FIND_PDFS"
    FIND_RESOURCES = "FIND_RESOURCES"
    PAGE_METADATA = "PAGE_METADATA"
    FAVICON = "FAVICON"
    SCREENSHOT = "SCREENSHOT"
    QR_GENERATE = "QR_GENERATE"
    QR_READ = "QR_READ"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

    @property
    def is_terminal(self) -> bool:
        return self in {
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.EXPIRED,
            JobStatus.CANCELLED,
        }


class Platform(StrEnum):
    """Known third-party platforms with dedicated extractors."""

    YOUTUBE = "youtube"
    VIMEO = "vimeo"
    DAILYMOTION = "dailymotion"
    REDDIT = "reddit"
    TIKTOK = "tiktok"
    TWITCH = "twitch"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
