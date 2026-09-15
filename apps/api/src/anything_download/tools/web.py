"""Web tools: analyze URLs and discover publicly referenced resources on a page."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from anything_download.analysis.engine import analyze_url, decode_html
from anything_download.analysis.models import FoundResource
from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.extractors.direct import SNIFF_BYTES, describe, download_to_file
from anything_download.extractors.generic_webpage import PageInfo, parse_page
from anything_download.net.client import raise_for_status
from anything_download.security.urls import ValidatedURL, validate_and_resolve
from anything_download.tools.base import (
    InputKind,
    NoOptions,
    Tool,
    ToolContext,
    ToolInput,
    ToolOutput,
    ToolSpec,
)
from anything_download.tools.common import make_zip, output_name, stem_of
from anything_download.tools.registry import register

_WEB = frozenset({ResourceType.WEBPAGE})
_URL = frozenset({InputKind.URL})


async def fetch_page(ctx: ToolContext, url: ValidatedURL) -> PageInfo:
    """Fetch an HTML page (bounded) and parse its resources."""
    response = await ctx.http.get(url, accept_encoding_identity=False)
    try:
        raise_for_status(response)
        head = await response.read_limited(SNIFF_BYTES)
        desc = describe(response.final_url, response, head)
        if desc.resource_type != ResourceType.WEBPAGE:
            raise AppError(
                ErrorCode.SOURCE_INVALID_CONTENT,
                f"The URL points to a {desc.resource_type.value.lower()} file, not a webpage.",
            )
        body, truncated = await response.read_all(ctx.settings.max_webpage_bytes)
        page = parse_page(
            decode_html(body, response.content_type),
            response.final_url.url,
            max_resources=ctx.settings.max_webpage_resources,
        )
        page.truncated = page.truncated or truncated
        return page
    finally:
        await response.aclose()


def _resources_payload(page: PageInfo, types: set[ResourceType] | None) -> dict[str, Any]:
    items = [r for r in page.resources if types is None or r.type in types]
    return {
        "title": page.title,
        "canonical": page.canonical,
        "count": len(items),
        "truncated": page.truncated,
        "resources": [r.model_dump() for r in items],
    }


class UrlAnalyzer(Tool):
    spec = ToolSpec(
        id="url-analyzer",
        category="web",
        capability=Capability.EXTRACT_METADATA,
        inputs=_URL,
        accepts=frozenset(ResourceType),
        options_model=NoOptions,
        fetch_input=False,
        output="data",
        order=50,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        url = source.require_url()
        analysis = await analyze_url(url.url, http=ctx.http, settings=ctx.settings)
        return ToolOutput(
            data=analysis.model_dump(mode="json"), resource_type=analysis.resource_type
        )


class _Finder(Tool):
    def __init__(
        self, tool_id: str, capability: Capability, types: set[ResourceType] | None, order: int
    ) -> None:
        self.types = types
        self.spec = ToolSpec(
            id=tool_id,
            category="web",
            capability=capability,
            inputs=_URL,
            accepts=_WEB,
            options_model=NoOptions,
            fetch_input=False,
            output="data",
            order=order,
        )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        page = await fetch_page(ctx, source.require_url())
        return ToolOutput(
            data=_resources_payload(page, self.types), resource_type=ResourceType.WEBPAGE
        )


class GalleryOptions(BaseModel):
    model_config = {"extra": "forbid"}
    max_images: int = Field(default=30, ge=1, le=100)
    min_bytes: int = Field(
        default=5 * 1024,
        ge=0,
        le=10 * 1024 * 1024,
        description="Skip images smaller than this (icons, trackers).",
    )


class WebsiteImageGallery(Tool):
    """Download the images referenced by a page into a single ZIP archive."""

    spec = ToolSpec(
        id="website-image-gallery",
        category="web",
        capability=Capability.FIND_IMAGES,
        inputs=_URL,
        accepts=_WEB,
        options_model=GalleryOptions,
        fetch_input=False,
        output="file+data",
        order=53,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, GalleryOptions)
        url = source.require_url()
        page = await fetch_page(ctx, url)
        images: list[FoundResource] = [
            r
            for r in page.resources
            if r.type == ResourceType.IMAGE and r.mime_type != "image/svg+xml"
        ]
        if not images:
            raise AppError(ErrorCode.SOURCE_INVALID_CONTENT, "No images were found on this page.")
        candidates = images[: options.max_images]
        per_image_limit = min(ctx.settings.max_file_size_bytes, 50 * 1024 * 1024)
        downloaded: list[tuple[Path, str]] = []
        skipped: list[dict[str, str]] = []
        budget = ctx.settings.max_file_size_bytes
        used = 0
        for i, res in enumerate(candidates, start=1):
            await ctx.check_cancelled()
            await ctx.report(
                "downloading",
                percent=(i - 1) / len(candidates) * 100,
                message=f"{i}/{len(candidates)}",
            )
            try:
                target = await validate_and_resolve(res.url, ctx.settings)
                local = await download_to_file(
                    ctx.http,
                    target,
                    ctx.work_dir / f"img-{i:03d}",
                    settings=ctx.settings,
                    max_bytes=min(per_image_limit, budget - used),
                )
            except AppError as exc:
                skipped.append({"url": res.url, "reason": exc.code.value})
                continue
            if local.resource_type != ResourceType.IMAGE or local.size_bytes < options.min_bytes:
                skipped.append(
                    {
                        "url": res.url,
                        "reason": "not_an_image"
                        if local.resource_type != ResourceType.IMAGE
                        else "too_small",
                    }
                )
                continue
            used += local.size_bytes
            downloaded.append((local.path, f"{i:03d}-{local.filename}"))
            if used >= budget:
                break
        if not downloaded:
            raise AppError(
                ErrorCode.SOURCE_INVALID_CONTENT,
                "None of the images on this page could be downloaded.",
                details={"skipped": skipped[:20]},
            )
        dest, name = output_name(ctx, f"{stem_of(source)}-images", "zip")
        await ctx.run_blocking(make_zip, dest, downloaded)
        data = {"downloaded": len(downloaded), "skipped": skipped[:50], "found": len(images)}
        notes = ["some_images_skipped"] if skipped else []
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="application/zip",
            resource_type=ResourceType.ARCHIVE,
            data=data,
            notes=notes,
        )


register(UrlAnalyzer())
register(_Finder("webpage-resource-extractor", Capability.FIND_RESOURCES, None, 51))
register(_Finder("image-url-extractor", Capability.FIND_IMAGES, {ResourceType.IMAGE}, 52))
register(WebsiteImageGallery())
register(
    _Finder(
        "website-pdf-finder", Capability.FIND_PDFS, {ResourceType.PDF, ResourceType.DOCUMENT}, 54
    )
)
register(_Finder("website-video-finder", Capability.FIND_VIDEOS, {ResourceType.VIDEO}, 55))
register(_Finder("website-audio-finder", Capability.FIND_AUDIO, {ResourceType.AUDIO}, 56))
