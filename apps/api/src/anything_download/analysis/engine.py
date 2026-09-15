"""Central URL analysis service.

    raw URL -> normalize -> validate (scheme/host/IP policy) -> detect platform
            -> otherwise probe the resource (streaming GET, first 8 KB)
            -> classify as direct file or webpage -> compute capabilities

Only *input* problems (malformed URL, blocked target, too long) raise; problems
with the *source* (404, unsupported platform content, DRM, ...) are returned as
an analysis with ``status`` = ``unsupported`` / ``restricted`` and a typed
``reason`` so the UI can explain instead of showing a broken button.
"""

from __future__ import annotations

import re

from anything_download.analysis.models import URLAnalysis
from anything_download.config import Settings, get_settings
from anything_download.domain import ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.extractors import direct as direct_extractor
from anything_download.extractors.generic_webpage import PageInfo, parse_page
from anything_download.extractors.registry import find_extractor
from anything_download.logging import get_logger
from anything_download.net.client import SafeHttpClient, raise_for_status
from anything_download.security.urls import ParsedURL, parse_url, validate_and_resolve
from anything_download.tools.base import InputKind
from anything_download.tools.registry import capabilities_for, runtime, tools_for

log = get_logger(__name__)

_META_CHARSET = re.compile(rb"<meta[^>]+charset=[\"']?([a-zA-Z0-9_-]+)", re.IGNORECASE)


async def analyze_url(
    raw: str, *, http: SafeHttpClient, settings: Settings | None = None
) -> URLAnalysis:
    settings = settings or get_settings()
    parsed = parse_url(raw, settings)

    extractor = find_extractor(parsed, settings)
    if extractor is not None:
        if not runtime().has("platform_extractors"):
            return _unsupported(
                parsed,
                AppError(
                    ErrorCode.TOOL_UNAVAILABLE, "Platform extraction is disabled on this server."
                ),
                source_kind="platform",
            )
        try:
            validated = await validate_and_resolve(parsed.url, settings)
            analysis = await extractor.analyze(validated, settings)
        except AppError as exc:
            if exc.code in {
                ErrorCode.BLOCKED_TARGET,
                ErrorCode.INVALID_URL,
                ErrorCode.URL_TOO_LONG,
            }:
                raise
            analysis = _unsupported(parsed, exc, source_kind="platform")
            analysis.platform = extractor.platform
            analysis.restrictions = sorted(set(extractor.restrictions()))
            return analysis
        if analysis.status == "ok":
            tools = tools_for(analysis.resource_type, InputKind.URL, platform_media=True)
            if analysis.resource_type == ResourceType.AUDIO:
                tools = [
                    t
                    for t in tools
                    if t.spec.category == "audio" or t.spec.id == "video-downloader"
                ]
            analysis.tools = [t.spec.id for t in tools]
            analysis.capabilities = capabilities_for(tools)
        return analysis

    try:
        response = await http.get(parsed.url)
    except AppError as exc:
        if exc.code in {
            ErrorCode.BLOCKED_TARGET,
            ErrorCode.INVALID_URL,
            ErrorCode.URL_TOO_LONG,
            ErrorCode.UNSUPPORTED_SCHEME,
        }:
            raise
        return _unsupported(parsed, exc, source_kind="direct")

    try:
        try:
            raise_for_status(response)
        except AppError as exc:
            return _unsupported(parsed, exc, source_kind="direct", final_url=response.final_url.url)
        head = await response.read_limited(direct_extractor.SNIFF_BYTES)
        description = direct_extractor.describe(response.final_url, response, head)
        final_url = response.final_url.url if response.final_url.url != parsed.url else None

        if description.resource_type == ResourceType.WEBPAGE:
            body, truncated = await response.read_all(settings.max_webpage_bytes)
            html = decode_html(body, response.content_type)
            page = parse_page(
                html, response.final_url.url, max_resources=settings.max_webpage_resources
            )
            return _webpage_analysis(
                parsed, page, final_url=final_url, truncated=truncated or page.truncated
            )

        tools = tools_for(description.resource_type, InputKind.URL)
        warnings = list(description.warnings)
        if (
            description.size_bytes is not None
            and description.size_bytes > settings.max_file_size_bytes
        ):
            warnings.append("exceeds_size_limit")
            tools = []
        return URLAnalysis(
            normalized_url=parsed.url,
            final_url=final_url,
            source_kind="direct",
            resource_type=description.resource_type,
            mime_type=description.mime_type,
            title=description.filename,
            filename=description.filename,
            size_bytes=description.size_bytes,
            tools=[t.spec.id for t in tools],
            capabilities=capabilities_for(tools),
            warnings=warnings,
            status="ok" if tools else "unsupported",
            reason=None
            if tools
            else AppError(
                ErrorCode.SOURCE_TOO_LARGE
                if "exceeds_size_limit" in warnings
                else ErrorCode.FILE_TYPE_UNSUPPORTED,
                "This file is larger than the configured size limit."
                if "exceeds_size_limit" in warnings
                else "No tools are available for this file type.",
            ).to_payload(),
        )
    finally:
        await response.aclose()


def _webpage_analysis(
    parsed: ParsedURL, page: PageInfo, *, final_url: str | None, truncated: bool
) -> URLAnalysis:
    tools = tools_for(ResourceType.WEBPAGE, InputKind.URL)
    counts = page.counts()
    tool_ids: list[str] = []
    for tool in tools:
        tid = tool.spec.id
        if tid == "website-image-gallery" and not counts.get("IMAGE"):
            continue
        if tid == "website-video-finder" and not counts.get("VIDEO"):
            continue
        if tid == "website-audio-finder" and not counts.get("AUDIO"):
            continue
        if tid == "website-pdf-finder" and not counts.get("PDF"):
            continue
        tool_ids.append(tid)
    kept = [t for t in tools if t.spec.id in tool_ids]
    warnings = ["page_truncated"] if truncated else []
    return URLAnalysis(
        normalized_url=parsed.url,
        final_url=final_url,
        source_kind="webpage",
        resource_type=ResourceType.WEBPAGE,
        mime_type="text/html",
        title=page.title,
        description=page.description,
        thumbnail=page.image,
        tools=tool_ids,
        capabilities=capabilities_for(kept),
        resource_counts=counts,
        warnings=warnings,
        status="ok",
    )


def _unsupported(
    parsed: ParsedURL, exc: AppError, *, source_kind: str, final_url: str | None = None
) -> URLAnalysis:
    restricted_codes = {
        ErrorCode.SOURCE_REQUIRES_AUTH,
        ErrorCode.SOURCE_DRM_PROTECTED,
        ErrorCode.SOURCE_PRIVATE,
        ErrorCode.SOURCE_GEO_RESTRICTED,
        ErrorCode.SOURCE_LIVE_STREAM,
        ErrorCode.SOURCE_FORBIDDEN,
    }
    return URLAnalysis(
        normalized_url=parsed.url,
        final_url=final_url,
        source_kind=source_kind,  # type: ignore[arg-type]
        resource_type=ResourceType.UNKNOWN,
        status="restricted" if exc.code in restricted_codes else "unsupported",
        reason=exc.to_payload(),
    )


def decode_html(body: bytes, content_type: str | None) -> str:
    charset = None
    if content_type:
        m = re.search(r"charset=[\"']?([a-zA-Z0-9_-]+)", content_type, re.IGNORECASE)
        if m:
            charset = m.group(1)
    if not charset:
        m2 = _META_CHARSET.search(body[:4096])
        if m2:
            charset = m2.group(1).decode("ascii", "ignore")
    for candidate in (charset, "utf-8", "cp1252"):
        if not candidate:
            continue
        try:
            return body.decode(candidate, errors="strict" if candidate != "cp1252" else "replace")
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")
