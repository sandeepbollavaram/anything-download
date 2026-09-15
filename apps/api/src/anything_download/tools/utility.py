"""Utility tools: page metadata, favicon, QR codes, screenshots, generic file download."""

from __future__ import annotations

from typing import Literal
from urllib.parse import urljoin

from pydantic import BaseModel, Field

from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.extractors.direct import download_to_file
from anything_download.security.urls import validate_and_resolve
from anything_download.tools.base import (
    InputKind,
    NoOptions,
    Tool,
    ToolContext,
    ToolInput,
    ToolOutput,
    ToolSpec,
)
from anything_download.tools.common import DownloadTool, output_name, stem_of
from anything_download.tools.registry import register
from anything_download.tools.web import fetch_page

_WEB = frozenset({ResourceType.WEBPAGE})
_URL = frozenset({InputKind.URL})


class UrlMetadata(Tool):
    spec = ToolSpec(
        id="url-metadata",
        category="utility",
        capability=Capability.PAGE_METADATA,
        inputs=_URL,
        accepts=_WEB,
        options_model=NoOptions,
        fetch_input=False,
        output="data",
        order=60,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        url = source.require_url()
        page = await fetch_page(ctx, url)
        data = {
            "url": url.url,
            "title": page.title,
            "description": page.description,
            "site_name": page.site_name,
            "canonical": page.canonical,
            "image": page.image,
            "favicons": page.favicons,
            **page.metadata,
            "resource_counts": page.counts(),
        }
        return ToolOutput(data=data, resource_type=ResourceType.WEBPAGE)


class FaviconDownloader(Tool):
    spec = ToolSpec(
        id="favicon-downloader",
        category="utility",
        capability=Capability.FAVICON,
        inputs=_URL,
        accepts=_WEB,
        options_model=NoOptions,
        fetch_input=False,
        order=61,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        url = source.require_url()
        candidates: list[str] = []
        try:
            page = await fetch_page(ctx, url)
            candidates.extend(page.favicons)
        except AppError as exc:
            if exc.code not in {ErrorCode.SOURCE_INVALID_CONTENT}:
                raise
        candidates.append(urljoin(url.origin + "/", "favicon.ico"))
        # Prefer larger / modern formats: PNG/SVG links first, ICO last.
        candidates.sort(key=lambda u: (u.lower().endswith(".ico"), "apple-touch" not in u))
        errors: list[str] = []
        for i, candidate in enumerate(candidates[:6]):
            await ctx.check_cancelled()
            try:
                target = await validate_and_resolve(candidate, ctx.settings)
                local = await download_to_file(
                    ctx.http,
                    target,
                    ctx.work_dir / f"icon-{i}",
                    settings=ctx.settings,
                    max_bytes=5 * 1024 * 1024,
                )
            except AppError as exc:
                errors.append(exc.code.value)
                continue
            if local.resource_type != ResourceType.IMAGE and local.mime_type not in {
                "image/x-icon",
                "image/vnd.microsoft.icon",
            }:
                errors.append("not_an_image")
                continue
            ext = local.filename.rsplit(".", 1)[-1] if "." in local.filename else "ico"
            dest, name = output_name(ctx, f"{url.host}-favicon", ext)
            local.path.replace(dest)
            return ToolOutput(
                file_path=dest,
                filename=name,
                mime_type=local.mime_type,
                resource_type=ResourceType.IMAGE,
                data={"source": candidate},
            )
        raise AppError(
            ErrorCode.SOURCE_NOT_FOUND,
            "No favicon could be found for this site.",
            details={"attempts": errors},
        )


class QrGenerateOptions(BaseModel):
    model_config = {"extra": "forbid"}
    format: Literal["png", "svg"] = "png"
    scale: int = Field(default=10, ge=1, le=40, description="Pixels per module (PNG).")
    border: int = Field(default=4, ge=0, le=16)
    error_correction: Literal["L", "M", "Q", "H"] = "M"


class QrGenerator(Tool):
    spec = ToolSpec(
        id="qr-generator",
        category="utility",
        capability=Capability.QR_GENERATE,
        inputs=frozenset({InputKind.TEXT}),
        accepts=frozenset(),
        options_model=QrGenerateOptions,
        fetch_input=False,
        order=62,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, QrGenerateOptions)
        text = (source.text or "").strip()
        if not text:
            raise AppError(ErrorCode.INVALID_OPTIONS, "Enter the text or URL to encode.")
        if len(text) > 2000:
            raise AppError(ErrorCode.INVALID_OPTIONS, "QR content is limited to 2000 characters.")
        import segno

        def work() -> tuple[str, str]:
            try:
                qr = segno.make(text, error=options.error_correction.lower())
            except (ValueError, segno.DataOverflowError) as exc:
                raise AppError(
                    ErrorCode.INVALID_OPTIONS, "The text is too long to fit in a QR code."
                ) from exc
            dest, name = output_name(ctx, "qr-code", options.format)
            if options.format == "svg":
                qr.save(
                    str(dest), kind="svg", scale=options.scale, border=options.border, xmldecl=True
                )
                return name, "image/svg+xml"
            qr.save(str(dest), kind="png", scale=options.scale, border=options.border)
            return name, "image/png"

        name, mime = await ctx.run_blocking(work)
        return ToolOutput(
            file_path=ctx.output_path(name),
            filename=name,
            mime_type=mime,
            resource_type=ResourceType.IMAGE,
            data={"version": None, "characters": len(text)},
        )


class QrReader(Tool):
    spec = ToolSpec(
        id="qr-reader",
        category="utility",
        capability=Capability.QR_READ,
        inputs=frozenset({InputKind.URL, InputKind.UPLOAD}),
        accepts=frozenset({ResourceType.IMAGE}),
        options_model=NoOptions,
        output="data",
        order=63,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        local = source.file
        if local.mime_type == "image/svg+xml":
            raise AppError(
                ErrorCode.FILE_TYPE_UNSUPPORTED,
                "SVG images cannot be scanned. Upload a raster image (PNG, JPEG, WebP).",
            )

        def work() -> list[dict[str, str]]:
            import zxingcpp
            from PIL import Image, UnidentifiedImageError

            Image.MAX_IMAGE_PIXELS = ctx.settings.max_image_pixels
            try:
                opened = Image.open(local.path)
                opened.load()
            except (
                UnidentifiedImageError,
                OSError,
                ValueError,
                Image.DecompressionBombError,
            ) as exc:
                raise AppError(ErrorCode.FILE_CORRUPT, "The image could not be decoded.") from exc
            img: Image.Image = opened.convert("RGB") if opened.mode not in {"RGB", "L"} else opened
            results = zxingcpp.read_barcodes(img)
            out: list[dict[str, str]] = []
            for r in results:
                out.append(
                    {
                        "format": str(r.format).split(".")[-1],
                        "text": r.text[:4000],
                        "content_type": str(r.content_type).split(".")[-1],
                    }
                )
            return out

        codes = await ctx.run_blocking(work)
        if not codes:
            raise AppError(
                ErrorCode.SOURCE_INVALID_CONTENT,
                "No QR code or barcode was detected in this image.",
            )
        return ToolOutput(
            data={"codes": codes, "count": len(codes)}, resource_type=ResourceType.IMAGE
        )


class ScreenshotOptions(BaseModel):
    model_config = {"extra": "forbid"}
    width: int = Field(default=1280, ge=320, le=1920)
    height: int = Field(default=800, ge=320, le=1600)
    full_page: bool = False


class WebpageScreenshot(Tool):
    spec = ToolSpec(
        id="webpage-screenshot",
        category="utility",
        capability=Capability.SCREENSHOT,
        inputs=_URL,
        accepts=_WEB,
        options_model=ScreenshotOptions,
        requires=frozenset({"browser"}),
        fetch_input=False,
        order=64,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, ScreenshotOptions)
        from anything_download.media.browser import screenshot

        url = source.require_url()
        dest, name = output_name(ctx, f"{stem_of(source)}-screenshot", "png")
        await ctx.report("rendering", force=True)
        await screenshot(
            url,
            dest,
            settings=ctx.settings,
            width=options.width,
            height=options.height,
            full_page=options.full_page,
            timeout=min(ctx.remaining_seconds, 90),
        )
        return ToolOutput(
            file_path=dest, filename=name, mime_type="image/png", resource_type=ResourceType.IMAGE
        )


register(UrlMetadata())
register(FaviconDownloader())
register(QrGenerator())
register(QrReader())
register(WebpageScreenshot())
register(
    DownloadTool(
        "file-downloader",
        "utility",
        {ResourceType.DOCUMENT, ResourceType.ARCHIVE, ResourceType.UNKNOWN},
        platform=False,
        order=65,
    )
)
