"""Public models returned by the URL analysis engine."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from anything_download.domain import Capability, Platform, ResourceType
from anything_download.errors import ErrorPayload

SourceKind = Literal["direct", "webpage", "platform"]
AnalysisStatus = Literal["ok", "unsupported", "restricted"]


class MediaFormat(BaseModel):
    """A downloadable rendition that the source actually exposes."""

    id: str = Field(description="Selector passed back as the 'format' option when downloading.")
    label: str = Field(description="Human readable label, e.g. '1080p', 'Audio only'.")
    kind: Literal["video", "audio", "video+audio", "image", "file"]
    ext: str | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    filesize: int | None = Field(default=None, description="Exact or approximate size in bytes.")
    filesize_is_estimate: bool = False
    vcodec: str | None = None
    acodec: str | None = None
    bitrate_kbps: float | None = None


class FoundResource(BaseModel):
    """A publicly referenced resource discovered on a webpage."""

    type: ResourceType
    url: str
    title: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    thumbnail: str | None = None
    downloadable: bool = True
    source: str = Field(
        description="Where it was found: img, video, audio, source, a, og, twitter, json-ld, link."
    )


class URLAnalysis(BaseModel):
    normalized_url: str
    final_url: str | None = Field(
        default=None, description="URL after following redirects, if different."
    )
    source_kind: SourceKind
    resource_type: ResourceType
    platform: Platform | None = None
    mime_type: str | None = None
    title: str | None = None
    description: str | None = None
    thumbnail: str | None = None
    duration_seconds: float | None = None
    size_bytes: int | None = None
    filename: str | None = Field(
        default=None, description="Suggested safe filename for direct files."
    )
    width: int | None = None
    height: int | None = None
    capabilities: list[Capability] = Field(default_factory=list)
    tools: list[str] = Field(
        default_factory=list, description="Applicable tool identifiers in display order."
    )
    formats: list[MediaFormat] = Field(default_factory=list)
    restrictions: list[str] = Field(
        default_factory=list, description="Machine readable restriction codes (e.g. 'live_stream')."
    )
    warnings: list[str] = Field(default_factory=list, description="Machine readable warning codes.")
    resource_counts: dict[str, int] = Field(
        default_factory=dict, description="For webpages: number of discovered resources per type."
    )
    status: AnalysisStatus = "ok"
    reason: ErrorPayload | None = Field(
        default=None, description="Populated when status is 'unsupported' or 'restricted'."
    )


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=8192)
