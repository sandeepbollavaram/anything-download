"""MIME type <-> extension <-> resource type mapping and magic-byte sniffing.

Extensions are never trusted alone: when bytes are available we sniff the file
signature and prefer it over both the declared ``Content-Type`` and the
extension.
"""

from __future__ import annotations

from dataclasses import dataclass

from anything_download.domain import ResourceType

# Canonical MIME types keyed by extension.
EXTENSION_MIME: dict[str, str] = {
    # video
    "mp4": "video/mp4",
    "m4v": "video/mp4",
    "webm": "video/webm",
    "mkv": "video/x-matroska",
    "mov": "video/quicktime",
    "avi": "video/x-msvideo",
    "ts": "video/mp2t",
    "3gp": "video/3gpp",
    "ogv": "video/ogg",
    # audio
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "aac": "audio/aac",
    "m4a": "audio/mp4",
    "ogg": "audio/ogg",
    "oga": "audio/ogg",
    "opus": "audio/ogg",
    "flac": "audio/flac",
    "weba": "audio/webm",
    # image
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
    "bmp": "image/bmp",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "heic": "image/heic",
    # documents
    "pdf": "application/pdf",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
    "xml": "application/xml",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xls": "application/vnd.ms-excel",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "ppt": "application/vnd.ms-powerpoint",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "epub": "application/epub+zip",
    "rtf": "application/rtf",
    "odt": "application/vnd.oasis.opendocument.text",
    # archives
    "zip": "application/zip",
    "gz": "application/gzip",
    "tgz": "application/gzip",
    "tar": "application/x-tar",
    "7z": "application/x-7z-compressed",
    "rar": "application/vnd.rar",
    "bz2": "application/x-bzip2",
    "xz": "application/x-xz",
    "zst": "application/zstd",
    # web
    "html": "text/html",
    "htm": "text/html",
}

MIME_EXTENSION: dict[str, str] = {}
for _ext, _mime in EXTENSION_MIME.items():
    MIME_EXTENSION.setdefault(_mime, _ext)
MIME_EXTENSION.update(
    {
        "image/jpg": "jpg",
        "image/pjpeg": "jpg",
        "audio/x-wav": "wav",
        "audio/wave": "wav",
        "audio/mp3": "mp3",
        "audio/x-m4a": "m4a",
        "audio/x-flac": "flac",
        "video/x-m4v": "mp4",
        "application/x-pdf": "pdf",
        "application/x-zip-compressed": "zip",
        "application/x-gzip": "gz",
        "application/x-rar-compressed": "rar",
        "application/xhtml+xml": "html",
        "image/vnd.microsoft.icon": "ico",
    }
)

_DOCUMENT_MIMES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/xml",
    "text/xml",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/epub+zip",
    "application/rtf",
    "application/vnd.oasis.opendocument.text",
}
_ARCHIVE_MIMES = {
    "application/zip",
    "application/x-zip-compressed",
    "application/gzip",
    "application/x-gzip",
    "application/x-tar",
    "application/x-7z-compressed",
    "application/vnd.rar",
    "application/x-rar-compressed",
    "application/x-bzip2",
    "application/x-xz",
    "application/zstd",
}


def normalize_mime(value: str | None) -> str | None:
    if not value:
        return None
    mime = value.split(";", 1)[0].strip().lower()
    if not mime or "/" not in mime:
        return None
    return {
        "image/jpg": "image/jpeg",
        "image/pjpeg": "image/jpeg",
        "audio/x-wav": "audio/wav",
        "audio/wave": "audio/wav",
        "audio/mp3": "audio/mpeg",
        "audio/x-m4a": "audio/mp4",
        "audio/x-flac": "audio/flac",
        "video/x-m4v": "video/mp4",
        "application/x-pdf": "application/pdf",
        "application/x-zip-compressed": "application/zip",
        "application/x-gzip": "application/gzip",
        "application/x-rar-compressed": "application/vnd.rar",
        "text/xml": "application/xml",
    }.get(mime, mime)


def resource_type_for_mime(mime: str | None) -> ResourceType:
    mime = normalize_mime(mime)
    if not mime:
        return ResourceType.UNKNOWN
    if mime in {"text/html", "application/xhtml+xml"}:
        return ResourceType.WEBPAGE
    if mime == "application/pdf":
        return ResourceType.PDF
    if mime.startswith("video/"):
        return ResourceType.VIDEO
    if mime.startswith("audio/"):
        return ResourceType.AUDIO
    if mime.startswith("image/"):
        return ResourceType.IMAGE
    if mime in _ARCHIVE_MIMES:
        return ResourceType.ARCHIVE
    if mime in _DOCUMENT_MIMES or mime.startswith("text/"):
        return ResourceType.DOCUMENT
    return ResourceType.UNKNOWN


def extension_for_mime(mime: str | None) -> str | None:
    mime = normalize_mime(mime)
    if not mime:
        return None
    return MIME_EXTENSION.get(mime)


def mime_for_extension(ext: str | None) -> str | None:
    if not ext:
        return None
    return EXTENSION_MIME.get(ext.lower().lstrip("."))


@dataclass(frozen=True)
class Signature:
    mime: str
    extension: str
    offset: int
    magic: bytes


_SIGNATURES: tuple[Signature, ...] = (
    Signature("application/pdf", "pdf", 0, b"%PDF-"),
    Signature("image/png", "png", 0, b"\x89PNG\r\n\x1a\n"),
    Signature("image/jpeg", "jpg", 0, b"\xff\xd8\xff"),
    Signature("image/gif", "gif", 0, b"GIF87a"),
    Signature("image/gif", "gif", 0, b"GIF89a"),
    Signature("image/bmp", "bmp", 0, b"BM"),
    Signature("image/tiff", "tiff", 0, b"II*\x00"),
    Signature("image/tiff", "tiff", 0, b"MM\x00*"),
    Signature("image/x-icon", "ico", 0, b"\x00\x00\x01\x00"),
    Signature("audio/mpeg", "mp3", 0, b"ID3"),
    Signature("audio/flac", "flac", 0, b"fLaC"),
    Signature("audio/ogg", "ogg", 0, b"OggS"),
    Signature("video/x-matroska", "mkv", 0, b"\x1a\x45\xdf\xa3"),
    Signature("application/zip", "zip", 0, b"PK\x03\x04"),
    Signature("application/zip", "zip", 0, b"PK\x05\x06"),
    Signature("application/gzip", "gz", 0, b"\x1f\x8b"),
    Signature("application/x-7z-compressed", "7z", 0, b"7z\xbc\xaf\x27\x1c"),
    Signature("application/vnd.rar", "rar", 0, b"Rar!\x1a\x07"),
    Signature("application/x-bzip2", "bz2", 0, b"BZh"),
    Signature("application/x-xz", "xz", 0, b"\xfd7zXZ\x00"),
    Signature("application/zstd", "zst", 0, b"\x28\xb5\x2f\xfd"),
    Signature("application/x-tar", "tar", 257, b"ustar"),
)

_ISO_BRANDS_VIDEO = {
    b"isom",
    b"iso2",
    b"iso4",
    b"iso5",
    b"iso6",
    b"mp41",
    b"mp42",
    b"avc1",
    b"dash",
    b"MSNV",
    b"NDSC",
    b"NDSH",
    b"NDSM",
    b"NDSP",
    b"NDSS",
    b"NDXC",
    b"NDXH",
    b"NDXM",
    b"NDXP",
    b"NDXS",
    b"mmp4",
    b"3gp4",
    b"3gp5",
    b"3gp6",
    b"3g2a",
    b"f4v ",
    b"iso3",
}


def sniff(data: bytes) -> tuple[str, str] | None:
    """Detect (mime, extension) from leading bytes. Returns None when unknown.

    ``data`` should contain at least the first 512 bytes of the file (more is fine).
    """
    if not data:
        return None
    for sig in _SIGNATURES:
        end = sig.offset + len(sig.magic)
        if len(data) >= end and data[sig.offset : end] == sig.magic:
            if sig.mime == "audio/ogg" and b"theora" in data[:512]:
                return "video/ogg", "ogv"
            if sig.mime == "video/x-matroska" and b"webm" in data[:64]:
                return "video/webm", "webm"
            return sig.mime, sig.extension
    # RIFF containers: WAV, WEBP, AVI
    if data[:4] == b"RIFF" and len(data) >= 12:
        kind = data[8:12]
        if kind == b"WAVE":
            return "audio/wav", "wav"
        if kind == b"WEBP":
            return "image/webp", "webp"
        if kind == b"AVI ":
            return "video/x-msvideo", "avi"
    # ISO base media file format: MP4 / MOV / M4A / AVIF / HEIC
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in {b"avif", b"avis"}:
            return "image/avif", "avif"
        if brand in {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}:
            return "image/heic", "heic"
        if brand == b"M4A ":
            return "audio/mp4", "m4a"
        if brand in {b"qt  "}:
            return "video/quicktime", "mov"
        if brand in _ISO_BRANDS_VIDEO or brand.startswith(b"mp4") or brand.startswith(b"3gp"):
            return "video/mp4", "mp4"
        return "video/mp4", "mp4"
    # MP3 without ID3 tag: MPEG frame sync
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0 and (data[1] & 0x06) != 0:
        return "audio/mpeg", "mp3"
    # MPEG transport stream
    if len(data) >= 189 and data[0] == 0x47 and data[188] == 0x47:
        return "video/mp2t", "ts"
    head = data[:1024].lstrip()
    lowered = head[:512].lower()
    if lowered.startswith((b"<!doctype html", b"<html", b"<head", b"<body")) or b"<html" in lowered:
        return "text/html", "html"
    if lowered.startswith(b"<?xml") and b"<svg" in data[:2048].lower():
        return "image/svg+xml", "svg"
    if lowered.startswith(b"<svg"):
        return "image/svg+xml", "svg"
    return None


def sniff_resource_type(data: bytes) -> ResourceType:
    detected = sniff(data)
    return resource_type_for_mime(detected[0]) if detected else ResourceType.UNKNOWN
