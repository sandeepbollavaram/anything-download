"""Image tools (Pillow based)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, model_validator

from anything_download.domain import Capability, ResourceType
from anything_download.errors import AppError, ErrorCode
from anything_download.tools.base import (
    InputKind,
    LocalInput,
    Tool,
    ToolContext,
    ToolInput,
    ToolOutput,
    ToolSpec,
)
from anything_download.tools.common import DownloadTool, output_name, stem_of
from anything_download.tools.registry import register

_IMAGE = frozenset({ResourceType.IMAGE})
_URL_UPLOAD = frozenset({InputKind.URL, InputKind.UPLOAD})

ImageFormat = Literal["jpeg", "png", "webp", "avif", "gif", "bmp", "tiff"]
_MIME: dict[str, str] = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "avif": "image/avif",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
}
_EXT: dict[str, str] = {
    "jpeg": "jpg",
    "png": "png",
    "webp": "webp",
    "avif": "avif",
    "gif": "gif",
    "bmp": "bmp",
    "tiff": "tiff",
}
_NO_ALPHA = {"jpeg", "bmp"}
_LOSSY = {"jpeg", "webp", "avif"}


def _open_image(local: LocalInput, max_pixels: int) -> Image.Image:
    if local.mime_type == "image/svg+xml":
        raise AppError(
            ErrorCode.FILE_TYPE_UNSUPPORTED, "SVG images cannot be processed by this tool."
        )
    Image.MAX_IMAGE_PIXELS = max_pixels
    try:
        img = Image.open(local.path)
        img.load()
    except Image.DecompressionBombError as exc:
        raise AppError(
            ErrorCode.FILE_TOO_LARGE, "The image has too many pixels to be processed safely."
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError(
            ErrorCode.FILE_CORRUPT,
            "The image could not be decoded. It may be corrupt or unsupported.",
        ) from exc
    if img.width * img.height > max_pixels:
        raise AppError(
            ErrorCode.FILE_TOO_LARGE, "The image has too many pixels to be processed safely."
        )
    if getattr(img, "n_frames", 1) > 1 and img.format != "GIF":
        img.seek(0)
    return img


def _source_format(local: LocalInput, img: Image.Image) -> str:
    fmt = (img.format or "").lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt in _MIME:
        return fmt
    mapping = {
        "image/jpeg": "jpeg",
        "image/png": "png",
        "image/webp": "webp",
        "image/avif": "avif",
        "image/gif": "gif",
        "image/bmp": "bmp",
        "image/tiff": "tiff",
    }
    return mapping.get(local.mime_type, "png")


def _prepare(
    img: Image.Image, target: str, *, keep_metadata: bool
) -> tuple[Image.Image, dict[str, object], list[str]]:
    """Apply EXIF orientation, fix modes for the target format and collect save kwargs."""
    notes: list[str] = []
    exif = img.info.get("exif")
    icc = img.info.get("icc_profile")
    img = ImageOps.exif_transpose(img) or img
    if target in _NO_ALPHA and img.mode in {"RGBA", "LA", "P", "PA"}:
        background = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        background.paste(rgba, mask=rgba.split()[-1])
        img = background
        notes.append("transparency_flattened")
    elif target in _NO_ALPHA and img.mode not in {"RGB", "L"}:
        img = img.convert("RGB")
    elif img.mode in {"P", "PA", "CMYK", "I;16", "I", "F"} and target != "gif":
        img = img.convert("RGBA" if "A" in img.mode or img.mode == "PA" else "RGB")
    kwargs: dict[str, object] = {}
    if icc:
        kwargs["icc_profile"] = icc
    if keep_metadata and exif and target in {"jpeg", "webp", "png", "tiff", "avif"}:
        kwargs["exif"] = exif
    elif exif:
        notes.append("metadata_removed")
    return img, kwargs, notes


def _save(
    img: Image.Image,
    dest: Path,
    target: str,
    *,
    quality: int | None,
    lossless: bool,
    extra: dict[str, object],
) -> None:
    kwargs: dict[str, object] = dict(extra)
    if target == "jpeg":
        kwargs.update(quality=quality or 85, optimize=True, progressive=True)
    elif target == "png":
        kwargs.update(optimize=True, compress_level=9)
    elif target == "webp":
        kwargs.update(quality=quality or 80, method=5, lossless=lossless)
    elif target == "avif":
        kwargs.update(quality=quality or 60, speed=6)
    elif target == "tiff":
        kwargs.update(compression="tiff_lzw")
    elif target == "gif":
        kwargs.update(optimize=True)
    try:
        img.save(dest, format=target.upper(), **kwargs)
    except (OSError, ValueError) as exc:
        raise AppError(
            ErrorCode.PROCESSING_FAILED, f"The image could not be encoded as {target.upper()}."
        ) from exc


# --------------------------------------------------------------------------
class CompressOptions(BaseModel):
    model_config = {"extra": "forbid"}
    quality: int = Field(default=75, ge=10, le=95, description="Lossy quality for JPEG/WebP/AVIF.")
    keep_metadata: bool = False


class ImageCompressor(Tool):
    spec = ToolSpec(
        id="image-compressor",
        category="image",
        capability=Capability.COMPRESS,
        inputs=_URL_UPLOAD,
        accepts=_IMAGE,
        options_model=CompressOptions,
        order=21,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, CompressOptions)
        local = source.file

        def work() -> tuple[Path, str, str, list[str]]:
            img = _open_image(local, ctx.settings.max_image_pixels)
            target = _source_format(local, img)
            if target in {"bmp", "tiff", "gif"}:
                target = "png" if img.mode in {"RGBA", "LA", "P"} else "jpeg"
            img, extra, notes = _prepare(img, target, keep_metadata=options.keep_metadata)
            if target == "png" and img.mode == "RGBA" and not _has_transparency(img):
                img = img.convert("RGB")
            if target == "png" and img.mode == "RGB":
                # Palette quantisation is a real size win for many PNGs.
                img = img.quantize(colors=256, method=Image.Quantize.MEDIANCUT).convert("P")
                notes.append("png_quantized_to_256_colors")
            dest, name = output_name(ctx, f"{stem_of(local)}-compressed", _EXT[target])
            _save(img, dest, target, quality=options.quality, lossless=False, extra=extra)
            if dest.stat().st_size >= local.size_bytes:
                notes.append("output_not_smaller")
            return dest, name, _MIME[target], notes

        dest, name, mime, notes = await ctx.run_blocking(work)
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type=mime,
            resource_type=ResourceType.IMAGE,
            notes=notes,
        )


def _has_transparency(img: Image.Image) -> bool:
    if img.mode not in {"RGBA", "LA"}:
        return False
    alpha = img.getchannel("A")
    extrema = alpha.getextrema()
    lo = extrema[0] if isinstance(extrema, tuple) else extrema
    return bool(lo < 255)  # type: ignore[operator]


# --------------------------------------------------------------------------
class ConvertOptions(BaseModel):
    model_config = {"extra": "forbid"}
    target: ImageFormat = "png"
    quality: int = Field(default=85, ge=10, le=100)
    keep_metadata: bool = False


class ImageConverter(Tool):
    spec = ToolSpec(
        id="image-converter",
        category="image",
        capability=Capability.CONVERT,
        inputs=_URL_UPLOAD,
        accepts=_IMAGE,
        options_model=ConvertOptions,
        order=22,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, ConvertOptions)
        local = source.file

        def work() -> tuple[Path, str, list[str]]:
            img = _open_image(local, ctx.settings.max_image_pixels)
            img, extra, notes = _prepare(img, options.target, keep_metadata=options.keep_metadata)
            dest, name = output_name(ctx, stem_of(local), _EXT[options.target])
            _save(
                img,
                dest,
                options.target,
                quality=options.quality,
                lossless=options.quality >= 100,
                extra=extra,
            )
            return dest, name, notes

        dest, name, notes = await ctx.run_blocking(work)
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type=_MIME[options.target],
            resource_type=ResourceType.IMAGE,
            notes=notes,
        )


class WebpOptions(BaseModel):
    model_config = {"extra": "forbid"}
    quality: int = Field(default=80, ge=10, le=100)
    lossless: bool = False
    keep_metadata: bool = False


class ImageToWebp(Tool):
    spec = ToolSpec(
        id="image-to-webp",
        category="image",
        capability=Capability.CONVERT,
        inputs=_URL_UPLOAD,
        accepts=_IMAGE,
        options_model=WebpOptions,
        order=24,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, WebpOptions)
        local = source.file

        def work() -> tuple[Path, str, list[str]]:
            img = _open_image(local, ctx.settings.max_image_pixels)
            img, extra, notes = _prepare(img, "webp", keep_metadata=options.keep_metadata)
            dest, name = output_name(ctx, stem_of(local), "webp")
            _save(
                img, dest, "webp", quality=options.quality, lossless=options.lossless, extra=extra
            )
            return dest, name, notes

        dest, name, notes = await ctx.run_blocking(work)
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="image/webp",
            resource_type=ResourceType.IMAGE,
            notes=notes,
        )


# --------------------------------------------------------------------------
class ResizeOptions(BaseModel):
    model_config = {"extra": "forbid"}
    width: int | None = Field(default=None, ge=1, le=10000)
    height: int | None = Field(default=None, ge=1, le=10000)
    percent: float | None = Field(default=None, gt=0, le=400)
    fit: Literal["contain", "cover", "exact"] = "contain"
    keep_metadata: bool = False

    @model_validator(mode="after")
    def _one_dimension(self) -> ResizeOptions:
        if self.percent is None and self.width is None and self.height is None:
            raise ValueError("Provide width, height or percent.")
        if self.percent is not None and (self.width or self.height):
            raise ValueError("Use either percent or explicit dimensions, not both.")
        return self


class ImageResizer(Tool):
    spec = ToolSpec(
        id="image-resizer",
        category="image",
        capability=Capability.RESIZE,
        inputs=_URL_UPLOAD,
        accepts=_IMAGE,
        options_model=ResizeOptions,
        order=23,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, ResizeOptions)
        local = source.file

        def work() -> tuple[Path, str, str, list[str], dict[str, int]]:
            img = _open_image(local, ctx.settings.max_image_pixels)
            target = _source_format(local, img)
            if target == "gif":
                target = "png"
            img, extra, notes = _prepare(img, target, keep_metadata=options.keep_metadata)
            ow, oh = img.size
            if options.percent is not None:
                nw = max(1, round(ow * options.percent / 100))
                nh = max(1, round(oh * options.percent / 100))
                img = img.resize((nw, nh), Image.Resampling.LANCZOS)
            else:
                w, h = options.width, options.height
                if w and h:
                    if options.fit == "exact":
                        img = img.resize((w, h), Image.Resampling.LANCZOS)
                    elif options.fit == "cover":
                        img = ImageOps.fit(img, (w, h), Image.Resampling.LANCZOS)
                    else:
                        img = ImageOps.contain(img, (w, h), Image.Resampling.LANCZOS)
                elif w:
                    img = img.resize((w, max(1, round(oh * w / ow))), Image.Resampling.LANCZOS)
                elif h:
                    img = img.resize((max(1, round(ow * h / oh)), h), Image.Resampling.LANCZOS)
            if img.width * img.height > ctx.settings.max_image_pixels:
                raise AppError(ErrorCode.FILE_TOO_LARGE, "The requested output size is too large.")
            dest, name = output_name(
                ctx, f"{stem_of(local)}-{img.width}x{img.height}", _EXT[target]
            )
            _save(img, dest, target, quality=90, lossless=False, extra=extra)
            return dest, name, _MIME[target], notes, {"width": img.width, "height": img.height}

        dest, name, mime, notes, dims = await ctx.run_blocking(work)
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type=mime,
            resource_type=ResourceType.IMAGE,
            notes=notes,
            data=dims,
        )


# --------------------------------------------------------------------------
class ImageToPdfOptions(BaseModel):
    model_config = {"extra": "forbid"}
    page_size: Literal["fit", "a4", "letter"] = "fit"
    margin_pt: int = Field(default=0, ge=0, le=144)


class ImageToPdf(Tool):
    spec = ToolSpec(
        id="image-to-pdf",
        category="image",
        capability=Capability.CONVERT_TO_PDF,
        inputs=frozenset({InputKind.URL, InputKind.UPLOAD, InputKind.UPLOADS}),
        accepts=_IMAGE,
        options_model=ImageToPdfOptions,
        order=25,
    )

    async def run(self, ctx: ToolContext, source: ToolInput, options: BaseModel) -> ToolOutput:
        assert isinstance(options, ImageToPdfOptions)
        if not source.files:
            raise AppError(ErrorCode.TOOL_INPUT_MISMATCH, "At least one image is required.")
        if len(source.files) > 200:
            raise AppError(
                ErrorCode.PAGE_LIMIT_EXCEEDED, "At most 200 images can be combined into one PDF."
            )
        files = list(source.files)

        def work() -> tuple[Path, str, list[str]]:
            pages: list[Image.Image] = []
            notes: list[str] = []
            for local in files:
                img = _open_image(local, ctx.settings.max_image_pixels)
                img, _extra, n = _prepare(img, "jpeg", keep_metadata=False)
                notes.extend(x for x in n if x not in notes)
                if img.mode != "RGB":
                    img = img.convert("RGB")
                if options.page_size != "fit":
                    pw, ph = (595, 842) if options.page_size == "a4" else (612, 792)
                    # Work at 2x for reasonable print resolution.
                    canvas = Image.new("RGB", (pw * 2, ph * 2), (255, 255, 255))
                    m = options.margin_pt * 2
                    fitted = ImageOps.contain(
                        img, (pw * 2 - 2 * m, ph * 2 - 2 * m), Image.Resampling.LANCZOS
                    )
                    canvas.paste(
                        fitted,
                        ((canvas.width - fitted.width) // 2, (canvas.height - fitted.height) // 2),
                    )
                    img = canvas
                pages.append(img)
            stem = stem_of(files[0]) if len(files) == 1 else "images"
            dest, name = output_name(ctx, stem, "pdf")
            first, rest = pages[0], pages[1:]
            try:
                first.save(dest, "PDF", save_all=bool(rest), append_images=rest, resolution=144.0)
            except (OSError, ValueError) as exc:
                raise AppError(
                    ErrorCode.PROCESSING_FAILED, "The PDF could not be written."
                ) from exc
            return dest, name, notes

        dest, name, notes = await ctx.run_blocking(work)
        return ToolOutput(
            file_path=dest,
            filename=name,
            mime_type="application/pdf",
            resource_type=ResourceType.PDF,
            notes=notes,
        )


register(DownloadTool("image-downloader", "image", {ResourceType.IMAGE}, platform=False, order=20))
register(ImageCompressor())
register(ImageConverter())
register(ImageResizer())
register(ImageToWebp())
register(ImageToPdf())
