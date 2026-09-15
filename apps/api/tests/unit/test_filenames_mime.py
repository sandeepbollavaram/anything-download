import pytest

from anything_download.detection.mime import (
    extension_for_mime,
    normalize_mime,
    resource_type_for_mime,
    sniff,
)
from anything_download.domain import ResourceType
from anything_download.security.filenames import content_disposition, sanitize_filename


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("..\\..\\windows\\system32\\cmd.exe", "cmd.exe"),
        ("/abs/path/file.pdf", "file.pdf"),
        ("C:\\Users\\x\\report.PDF", "report.pdf"),
        ("my video (final).MP4", "my-video-(final).mp4"),
        ("CON", "file-CON"),
        ("nul.txt", "file-nul.txt"),
        ("....", "download"),
        ("", "download"),
        ("a\x00b\x1f.txt", "ab.txt"),
        ("héllo wörld.png", "héllo-wörld.png"),
        ("<script>alert(1)</script>.html", "script.html"),  # '/' is a path separator
        ("x" * 300 + ".jpg", "x" * 120 + ".jpg"),
        ("name.tar.gz", "name.tar.gz"),
        ("noext", "noext"),
        ("weird.EXE.", "weird.exe"),
    ],
)
def test_sanitize(raw: str, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_sanitize_with_forced_ext() -> None:
    assert sanitize_filename("photo.png", ext="webp") == "photo.webp"
    assert sanitize_filename("photo", ext=".jpg") == "photo.jpg"
    assert sanitize_filename("x", ext="not valid!") == "x"


def test_content_disposition_header_is_safe() -> None:
    header = content_disposition('bad"name\r\nX: y.pdf')
    assert "\r" not in header and "\n" not in header
    assert header.startswith("attachment;")
    assert "filename*=UTF-8''" in header


@pytest.mark.parametrize(
    ("data", "mime"),
    [
        (b"%PDF-1.7 rest", "application/pdf"),
        (b"\x89PNG\r\n\x1a\n" + b"\0" * 20, "image/png"),
        (b"\xff\xd8\xff\xe0" + b"\0" * 20, "image/jpeg"),
        (b"GIF89a" + b"\0" * 20, "image/gif"),
        (b"RIFF\0\0\0\0WEBPVP8 ", "image/webp"),
        (b"RIFF\0\0\0\0WAVEfmt ", "audio/wav"),
        (b"\0\0\0\x18ftypisom\0\0\0\0", "video/mp4"),
        (b"\0\0\0\x18ftypavif\0\0\0\0", "image/avif"),
        (b"\0\0\0\x18ftypM4A \0\0\0\0", "audio/mp4"),
        (b"\0\0\0\x18ftypqt  \0\0\0\0", "video/quicktime"),
        (
            b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01B\xf7\x81\x01B\xf2\x81\x04B\xf3\x81\x08B\x82\x84webm",
            "video/webm",
        ),
        (
            b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01B\xf7\x81\x01B\xf2\x81\x04B\xf3\x81\x08B\x82\x88matroska",
            "video/x-matroska",
        ),
        (b"ID3\x04\0\0\0\0\0\0", "audio/mpeg"),
        (b"\xff\xfb\x90\x00" + b"\0" * 20, "audio/mpeg"),
        (b"fLaC\0\0\0\x22", "audio/flac"),
        (b"OggS\0\x02" + b"\0" * 30, "audio/ogg"),
        (b"PK\x03\x04" + b"\0" * 20, "application/zip"),
        (b"\x1f\x8b\x08" + b"\0" * 20, "application/gzip"),
        (b"7z\xbc\xaf\x27\x1c" + b"\0" * 10, "application/x-7z-compressed"),
        (b"Rar!\x1a\x07\x01\0", "application/vnd.rar"),
        (b"<!DOCTYPE html><html><head></head></html>", "text/html"),
        (b"\n  <html lang=en><body>x</body></html>", "text/html"),
        (b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>', "image/svg+xml"),
    ],
)
def test_sniff(data: bytes, mime: str) -> None:
    result = sniff(data)
    assert result is not None
    assert result[0] == mime


def test_sniff_unknown() -> None:
    assert sniff(b"hello world plain text") is None
    assert sniff(b"") is None


@pytest.mark.parametrize(
    ("mime", "rtype"),
    [
        ("video/mp4", ResourceType.VIDEO),
        ("audio/mpeg", ResourceType.AUDIO),
        ("image/webp", ResourceType.IMAGE),
        ("application/pdf", ResourceType.PDF),
        ("text/html; charset=utf-8", ResourceType.WEBPAGE),
        ("application/zip", ResourceType.ARCHIVE),
        ("text/plain", ResourceType.DOCUMENT),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ResourceType.DOCUMENT,
        ),
        ("application/octet-stream", ResourceType.UNKNOWN),
        (None, ResourceType.UNKNOWN),
    ],
)
def test_resource_type(mime: str | None, rtype: ResourceType) -> None:
    assert resource_type_for_mime(mime) == rtype


def test_normalize_and_extension() -> None:
    assert normalize_mime("Image/JPG; charset=x") == "image/jpeg"
    assert extension_for_mime("image/jpeg") == "jpg"
    assert extension_for_mime("audio/x-wav") == "wav"
    assert extension_for_mime("application/unknown") is None
