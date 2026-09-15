"""Safe filename generation.

Filenames derived from untrusted sources (URL paths, page titles,
``Content-Disposition`` headers) are reduced to a conservative character set,
stripped of path components and reserved device names, and capped in length.
"""

from __future__ import annotations

import re
import unicodedata

_WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
)
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f\x7f]')
_MULTI_SPACE = re.compile(r"[\s_]+")
_MULTI_DASH = re.compile(r"-{2,}")
_MAX_BASENAME = 120
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")


def sanitize_extension(ext: str | None) -> str:
    """Return a lowercase extension without the dot, or an empty string."""
    if not ext:
        return ""
    ext = ext.strip().lstrip(".").lower()
    return ext if _EXT_RE.match(ext) else ""


def sanitize_filename(
    name: str | None, *, fallback: str = "download", ext: str | None = None
) -> str:
    """Produce a safe filename such as ``my-video.mp4``.

    * path separators and traversal sequences are removed
    * control and shell-hostile characters are removed
    * unicode is NFKC-normalized (non-ASCII letters are kept)
    * reserved Windows device names are prefixed
    * length is bounded
    """
    raw = (name or "").strip()
    # Drop any directory components from either separator style.
    raw = raw.replace("\\", "/").rsplit("/", 1)[-1]
    raw = unicodedata.normalize("NFKC", raw)
    raw = _ILLEGAL.sub("", raw)
    raw = raw.replace("..", ".").strip(" .")

    base, sep, given_ext = raw.rpartition(".")
    if not sep:
        base, given_ext = raw, ""
    final_ext = sanitize_extension(ext) or sanitize_extension(given_ext)
    if ext is None and not final_ext:
        base = raw  # no usable extension, keep everything as the base name

    base = _MULTI_SPACE.sub("-", base.strip(" .-"))
    base = _MULTI_DASH.sub("-", base).strip("-.")
    if not base or base.upper() in _WINDOWS_RESERVED or all(ch == "." for ch in base):
        base = fallback if not base else f"file-{base}"
    if len(base) > _MAX_BASENAME:
        base = base[:_MAX_BASENAME].rstrip("-. ")
    return f"{base}.{final_ext}" if final_ext else base


def content_disposition(filename: str, *, inline: bool = False) -> str:
    """Build a ``Content-Disposition`` header with an ASCII fallback + RFC 5987 UTF-8 form."""
    from urllib.parse import quote

    safe = sanitize_filename(filename)
    ascii_fallback = safe.encode("ascii", "ignore").decode("ascii") or "download"
    ascii_fallback = ascii_fallback.replace('"', "")
    disposition = "inline" if inline else "attachment"
    return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{quote(safe)}"
