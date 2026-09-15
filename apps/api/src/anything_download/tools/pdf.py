"""PDF tools (pikepdf for structure, pypdfium2 for rendering and text)."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Literal

import pikepdf
import pypdfium2 as pdfium
from PIL import Image
from pydantic import BaseModel, Field

from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.tools.base import (
    InputKind,
    LocalInput,
    NoOptions,
    Tool,
    ToolContext,
    ToolInput,
    ToolOutput,
    ToolSpec,
)
from anything_download.tools.common import DownloadTool, make_zip, output_name, stem_of
from anything_download.tools.registry import register

_PDF = frozenset({ResourceType.PDF})
_URL_UPLOAD = frozenset({InputKind.URL, InputKind.UPLOAD})


def open_pdf(local: LocalInput, max_pages: int) -> pikepdf.Pdf:
    """Open and validate a PDF, rejecting encrypted or oversized documents."""
    try:
        pdf = pikepdf.open(local.path)
    except pikepdf.PasswordError as exc:
        raise AppError(
            ErrorCode.FILE_TYPE_UNSUPPORTED,
            "This PDF is password protected and cannot be processed.",
        ) from exc
    except (pikepdf.PdfError, RuntimeError, ValueError, OSError) as exc:
        raise AppError(
            ErrorCode.FILE_CORRUPT, "The PDF could not be read. It may be corrupt."
        ) from exc
    if pdf.is_encrypted:
        pdf.close()
        raise AppError(ErrorCode.FILE_TYPE_UNSUPPORTED, "Encrypted PDFs cannot be processed.")
    if len(pdf.pages) > max_pages:
        count = len(pdf.pages)
        pdf.close()
        raise AppError(
            ErrorCode.PAGE_LIMIT_EXCEEDED, f"This PDF has {count} pages; the limit is {max_pages}."
        )
    if len(pdf.pages) == 0:
        pdf.close()
        raise AppError(ErrorCode.FILE_CORRUPT, "This PDF has no pages.")
    return pdf


def parse_page_ranges(spec: str, page_count: int) -> list[int]:
    """Parse '1-3,5,8-' into zero-based page indexes (bounded, ordered, unique)."""
    pages: list[int] = []
    spec = spec.replace(" ", "")
    if not spec:
        raise AppError(ErrorCode.INVALID_OPTIONS, "No pages were specified.")
    for part in spec.split(","):
        if not part:
            continue
        m = re.fullmatch(r"(\d+)?(-)?(\d+)?", part)
        if not m or (m.group(1) is None and m.group(3) is None):
            raise AppError(ErrorCode.INVALID_OPTIONS, f"Invalid page range '{part}'.")
        start = int(m.group(1)) if m.group(1) else 1
        end = (int(m.group(3)) if m.group(3) else page_count) if m.group(2) else start
        if start < 1 or end < start:
            raise AppError(ErrorCode.INVALID_OPTIONS, f"Invalid page range '{part}'.")
        if start > page_count:
            raise AppError(
                ErrorCode.INVALID_OPTIONS, f"Page {start} is beyond the last page ({page_count})."
            )
        end = min(end, page_count)
        for p in range(start - 1, end):
            if p not in pages:
                pages.append(p)
    if not pages:
        raise AppError(ErrorCode.INVALID_OPTIONS, "No pages were selected.")
    return pages


# --------------------------------------------------------------------------
class PdfCompressOptions(BaseModel):
    model_config = {"extra": "forbid"}
    level: Literal["light", "medium", "strong"] = "medium"


_LEVELS = {"light": (85, 2200), "medium": (70, 1600), "strong": (50, 1100)}


def _recompress_images(pdf: pikepdf.Pdf, quality: int, max_dim: int, max_pixels: int) -> int:
    """Re-encode large raster images as JPEG (optionally downscaled). Returns count changed."""
    changed = 0
    seen: set[int] = set()
    for page in pdf.pages:
        for _name, raw in page.images.items():
            try:
                objgen = raw.objgen
            except (AttributeError, ValueError):
                objgen = None
            key = hash(objgen) if objgen else id(raw)
            if key in seen:
                continue
            seen.add(key)
            try:
                pdfimage = pikepdf.PdfImage(raw)
                width, height = pdfimage.width, pdfimage.height
                if width * height < 40_000 or width * height > max_pixels:
                    continue
                if (
                    pdfimage.image_mask
                    or "/SMask" in raw
                    or "/Mask" in raw
                    or pdfimage.is_separation
                    or pdfimage.is_device_n
                ):
                    continue
                if pdfimage.bits_per_component not in (8, None) and not pdfimage.indexed:
                    continue
                original_size = len(raw.read_raw_bytes())
                pil = pdfimage.as_pil_image()
            except Exception:  # noqa: BLE001, S112 - unsupported image flavours are skipped
                continue
            if pil.mode not in {"RGB", "L"}:
                pil = pil.convert("RGB")
            scale = min(1.0, max_dim / max(pil.width, pil.height))
            if scale < 1.0:
                pil = pil.resize(
                    (max(1, round(pil.width * scale)), max(1, round(pil.height * scale))),
                    Image.Resampling.LANCZOS,
                )
            buf = io.BytesIO()
            pil.save(buf, "JPEG", quality=quality, optimize=True)
            data = buf.getvalue()
            if len(data) >= original_size * 0.9:
                continue
            raw.write(data, filter=pikepdf.Name("/DCTDecode"))
            raw.Width = pil.width
            raw.Height = pil.height
            raw.BitsPerComponent = 8
            raw.ColorSpace = (
                pikepdf.Name("/DeviceRGB") if pil.mode == "RGB" else pikepdf.Name("/DeviceGray")
            )
            for k in ("/Decode", "/DecodeParms", "/Interpolate"):
                if k in raw:
                    del raw[k]
            changed += 1
    return changed


class PdfCompressor(Tool):
    spec = ToolSpec(
        id="pdf-compressor",
        category="pdf",
        capability=Capability.COMPRESS,
        inputs=_URL_UPLOAD,
        accepts=_PDF,
        options_model=PdfCompressOptions,
        order=31,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, PdfCompressOptions)
        local = source.file
        quality, max_dim = _LEVELS[options.level]

        def work() -> tuple[Path, str, list[str], dict[str, int]]:
            notes: list[str] = []
            with open_pdf(local, ctx.settings.max_pdf_pages) as pdf:
                changed = _recompress_images(pdf, quality, max_dim, ctx.settings.max_image_pixels)
                for page in pdf.pages:
                    try:
                        page.remove_unreferenced_resources()
                    except Exception:  # noqa: BLE001, S112 - best effort; the page is kept as is
                        continue
                pdf.remove_unreferenced_resources()
                dest, name = output_name(ctx, f"{stem_of(local)}-compressed", "pdf")
                try:
                    pdf.save(
                        dest,
                        compress_streams=True,
                        recompress_flate=True,
                        object_stream_mode=pikepdf.ObjectStreamMode.generate,
                        linearize=False,
                    )
                except (pikepdf.PdfError, RuntimeError) as exc:
                    raise AppError(
                        ErrorCode.PROCESSING_FAILED, "The compressed PDF could not be written."
                    ) from exc
            if changed:
                notes.append("images_recompressed")
            if dest.stat().st_size >= local.size_bytes:
                notes.append("output_not_smaller")
            return dest, name, notes, {"images_recompressed": changed}

        dest, name, notes, data = await ctx.run_blocking(work)
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="application/pdf",
            resource_type=ResourceType.PDF,
            notes=notes,
            data=data,
        )


# --------------------------------------------------------------------------
class PdfMerger(Tool):
    spec = ToolSpec(
        id="pdf-merger",
        category="pdf",
        capability=Capability.MERGE,
        inputs=frozenset({InputKind.UPLOADS}),
        accepts=_PDF,
        options_model=NoOptions,
        order=32,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        if len(source.files) < 2:
            raise AppError(ErrorCode.TOOL_INPUT_MISMATCH, "Select at least two PDF files to merge.")
        files = list(source.files)

        def work() -> tuple[Path, str, int]:
            total = 0
            out = pikepdf.Pdf.new()
            opened: list[pikepdf.Pdf] = []
            try:
                for local in files:
                    pdf = open_pdf(local, ctx.settings.max_pdf_pages)
                    opened.append(pdf)
                    total += len(pdf.pages)
                    if total > ctx.settings.max_pdf_pages:
                        raise AppError(
                            ErrorCode.PAGE_LIMIT_EXCEEDED,
                            f"The merged PDF would exceed {ctx.settings.max_pdf_pages} pages.",
                        )
                    out.pages.extend(pdf.pages)
                dest, name = output_name(ctx, "merged", "pdf")
                out.save(
                    dest,
                    compress_streams=True,
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                )
            finally:
                for pdf in opened:
                    pdf.close()
                out.close()
            return dest, name, total

        dest, name, total = await ctx.run_blocking(work)
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="application/pdf",
            resource_type=ResourceType.PDF,
            data={"pages": total, "files": len(files)},
        )


# --------------------------------------------------------------------------
class PdfSplitOptions(BaseModel):
    model_config = {"extra": "forbid"}
    mode: Literal["ranges", "each", "chunks"] = "ranges"
    pages: str = Field(default="", description="For mode 'ranges': e.g. '1-3,5,8-'.")
    chunk_size: int = Field(default=10, ge=1, le=500, description="For mode 'chunks'.")


class PdfSplitter(Tool):
    spec = ToolSpec(
        id="pdf-splitter",
        category="pdf",
        capability=Capability.SPLIT,
        inputs=_URL_UPLOAD,
        accepts=_PDF,
        options_model=PdfSplitOptions,
        order=33,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, PdfSplitOptions)
        local = source.file
        stem = stem_of(local)

        def work() -> tuple[Path, str, str, dict[str, int]]:
            with open_pdf(local, ctx.settings.max_pdf_pages) as pdf:
                count = len(pdf.pages)
                if options.mode == "ranges":
                    indexes = parse_page_ranges(options.pages, count)
                    out = pikepdf.Pdf.new()
                    for i in indexes:
                        out.pages.append(pdf.pages[i])
                    dest, name = output_name(ctx, f"{stem}-pages", "pdf")
                    out.save(dest, compress_streams=True)
                    out.close()
                    return dest, name, "application/pdf", {"pages": len(indexes)}
                groups: list[list[int]]
                if options.mode == "each":
                    groups = [[i] for i in range(count)]
                else:
                    groups = [
                        list(range(i, min(i + options.chunk_size, count)))
                        for i in range(0, count, options.chunk_size)
                    ]
                if len(groups) == 1:
                    out = pikepdf.Pdf.new()
                    for i in groups[0]:
                        out.pages.append(pdf.pages[i])
                    dest, name = output_name(ctx, f"{stem}-part-1", "pdf")
                    out.save(dest, compress_streams=True)
                    out.close()
                    return dest, name, "application/pdf", {"parts": 1}
                parts: list[tuple[Path, str]] = []
                for n, group in enumerate(groups, start=1):
                    out = pikepdf.Pdf.new()
                    for i in group:
                        out.pages.append(pdf.pages[i])
                    part_name = (
                        f"{stem}-part-{n:03d}.pdf"
                        if options.mode == "chunks"
                        else f"{stem}-page-{group[0] + 1:03d}.pdf"
                    )
                    part_path = ctx.work_path(part_name)
                    out.save(part_path, compress_streams=True)
                    out.close()
                    parts.append((part_path, part_name))
                dest, name = output_name(ctx, f"{stem}-split", "zip")
                make_zip(dest, parts)
                return dest, name, "application/zip", {"parts": len(parts)}

        dest, name, mime, data = await ctx.run_blocking(work)
        rtype = ResourceType.PDF if mime == "application/pdf" else ResourceType.ARCHIVE
        return ToolOutput(
            file_path=dest, filename=name, mime_type=mime, resource_type=rtype, data=data
        )


# --------------------------------------------------------------------------
class PdfToTextOptions(BaseModel):
    model_config = {"extra": "forbid"}
    pages: str = Field(
        default="", description="Optional page ranges, e.g. '1-5'. Empty means all pages."
    )


class PdfToText(Tool):
    spec = ToolSpec(
        id="pdf-to-text",
        category="pdf",
        capability=Capability.PDF_TO_TEXT,
        inputs=_URL_UPLOAD,
        accepts=_PDF,
        options_model=PdfToTextOptions,
        output="file+data",
        order=34,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, PdfToTextOptions)
        local = source.file

        def work() -> tuple[Path, str, dict[str, object]]:
            with open_pdf(local, ctx.settings.max_pdf_pages) as pdf:
                count = len(pdf.pages)
            indexes = (
                parse_page_ranges(options.pages, count)
                if options.pages.strip()
                else list(range(count))
            )
            doc = pdfium.PdfDocument(str(local.path))
            chunks: list[str] = []
            chars = 0
            try:
                for i in indexes:
                    page = doc[i]
                    textpage = page.get_textpage()
                    try:
                        text = textpage.get_text_range()
                    finally:
                        textpage.close()
                        page.close()
                    chars += len(text)
                    chunks.append(text)
            finally:
                doc.close()
            dest, name = output_name(ctx, stem_of(local), "txt")
            dest.write_text("\n\n".join(chunks), encoding="utf-8")
            preview = "\n\n".join(chunks)[:2000]
            data: dict[str, object] = {
                "pages": len(indexes),
                "characters": chars,
                "preview": preview,
            }
            if chars == 0:
                data["note"] = "no_text_layer"
            return dest, name, data

        dest, name, data = await ctx.run_blocking(work)
        notes = ["no_text_layer"] if data.get("characters") == 0 else []
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="text/plain",
            resource_type=ResourceType.DOCUMENT,
            data=data,
            notes=notes,
        )


# --------------------------------------------------------------------------
class PdfToImagesOptions(BaseModel):
    model_config = {"extra": "forbid"}
    format: Literal["png", "jpg", "webp"] = "png"
    dpi: int = Field(default=144, ge=36, le=300)
    pages: str = Field(
        default="", description="Optional page ranges. Empty means all pages (max 100)."
    )


class PdfToImages(Tool):
    spec = ToolSpec(
        id="pdf-to-images",
        category="pdf",
        capability=Capability.PDF_TO_IMAGES,
        inputs=_URL_UPLOAD,
        accepts=_PDF,
        options_model=PdfToImagesOptions,
        order=35,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, PdfToImagesOptions)
        local = source.file
        mime = {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[options.format]

        def work() -> tuple[Path, str, str, int]:
            with open_pdf(local, ctx.settings.max_pdf_pages) as pdf:
                count = len(pdf.pages)
            indexes = (
                parse_page_ranges(options.pages, count)
                if options.pages.strip()
                else list(range(count))
            )
            if len(indexes) > 100:
                raise AppError(
                    ErrorCode.PAGE_LIMIT_EXCEEDED,
                    "At most 100 pages can be rendered per job. Use the pages option to select a range.",
                )
            doc = pdfium.PdfDocument(str(local.path))
            rendered: list[tuple[Path, str]] = []
            stem = stem_of(local)
            try:
                for i in indexes:
                    page = doc[i]
                    try:
                        w, h = page.get_size()
                        scale = options.dpi / 72
                        if (w * scale) * (h * scale) > ctx.settings.max_image_pixels:
                            raise AppError(
                                ErrorCode.FILE_TOO_LARGE,
                                "The page would render to too many pixels at this DPI. Lower the DPI.",
                            )
                        bitmap = page.render(scale=scale)
                        pil = bitmap.to_pil()
                    finally:
                        page.close()
                    if options.format == "jpg" and pil.mode != "RGB":
                        pil = pil.convert("RGB")
                    fname = f"{stem}-page-{i + 1:03d}.{options.format}"
                    path = ctx.work_path(fname) if len(indexes) > 1 else ctx.output_path(fname)
                    save_kwargs: dict[str, object] = (
                        {"quality": 90} if options.format in {"jpg", "webp"} else {"optimize": True}
                    )
                    pil.save(
                        path,
                        format={"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[options.format],
                        **save_kwargs,
                    )
                    rendered.append((path, fname))
            finally:
                doc.close()
            if len(rendered) == 1:
                path, fname = rendered[0]
                return path, fname, mime, 1
            dest, name = output_name(ctx, f"{stem}-pages", "zip")
            make_zip(dest, rendered)
            return dest, name, "application/zip", len(rendered)

        dest, name, out_mime, n = await ctx.run_blocking(work)
        rtype = ResourceType.IMAGE if out_mime.startswith("image/") else ResourceType.ARCHIVE
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type=out_mime,
            resource_type=rtype,
            data={"pages": n},
        )


# --------------------------------------------------------------------------
class UrlToPdfOptions(BaseModel):
    model_config = {"extra": "forbid"}
    page_size: Literal["A4", "Letter"] = "A4"
    landscape: bool = False
    print_background: bool = True


class UrlToPdf(Tool):
    spec = ToolSpec(
        id="url-to-pdf",
        category="pdf",
        capability=Capability.CONVERT_TO_PDF,
        inputs=frozenset({InputKind.URL}),
        accepts=frozenset({ResourceType.WEBPAGE}),
        options_model=UrlToPdfOptions,
        requires=frozenset({"browser"}),
        fetch_input=False,
        order=36,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, UrlToPdfOptions)
        from anything_download.media.browser import render_pdf

        url = source.require_url()
        dest, name = output_name(ctx, stem_of(source), "pdf")
        await ctx.report("rendering", force=True)
        await render_pdf(
            url,
            dest,
            settings=ctx.settings,
            page_size=options.page_size,
            landscape=options.landscape,
            print_background=options.print_background,
            timeout=min(ctx.remaining_seconds, 90),
        )
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="application/pdf",
            resource_type=ResourceType.PDF,
        )


register(DownloadTool("pdf-downloader", "pdf", {ResourceType.PDF}, platform=False, order=30))
register(PdfCompressor())
register(PdfMerger())
register(PdfSplitter())
register(PdfToText())
register(PdfToImages())
register(UrlToPdf())
