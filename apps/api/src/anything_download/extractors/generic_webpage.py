"""Generic webpage extractor.

Parses an HTML document (bounded in size) and lists publicly referenced
resources: images, video/audio elements, ``<source>`` entries, links to
documents, Open Graph / Twitter card images and JSON-LD media references.

No JavaScript is executed and no crawling happens: only the single document
the user supplied is inspected.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from bs4.element import Tag

from anything_download.analysis.models import FoundResource
from anything_download.detection.mime import (
    EXTENSION_MIME,
    mime_for_extension,
    normalize_mime,
    resource_type_for_mime,
)
from anything_download.domain import ResourceType
from anything_download.security.urls import is_blocked_hostname, is_blocked_ip

_IMAGE_EXT = {"jpg", "jpeg", "png", "gif", "webp", "avif", "bmp", "svg", "ico", "tif", "tiff"}
_VIDEO_EXT = {"mp4", "webm", "mkv", "mov", "m4v", "ogv", "avi"}
_AUDIO_EXT = {"mp3", "wav", "aac", "m4a", "ogg", "oga", "opus", "flac", "weba"}
_DOC_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "epub", "odt", "rtf", "csv", "txt"}
_ARCHIVE_EXT = {"zip", "gz", "tgz", "tar", "7z", "rar", "bz2", "xz", "zst"}
_LINK_EXT = (
    _VIDEO_EXT
    | _AUDIO_EXT
    | _DOC_EXT
    | _ARCHIVE_EXT
    | {"jpg", "jpeg", "png", "gif", "webp", "avif", "svg"}
)

_SRCSET_RE = re.compile(r"\s*([^\s,]+)(?:\s+[\d.]+[wx])?\s*(?:,|$)")


@dataclass
class PageInfo:
    title: str | None = None
    description: str | None = None
    canonical: str | None = None
    image: str | None = None
    site_name: str | None = None
    favicons: list[str] = field(default_factory=list)
    resources: list[FoundResource] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    truncated: bool = False

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.resources:
            out[r.type.value] = out.get(r.type.value, 0) + 1
        return out


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:500] or None


def _absolute(base: str, candidate: str | None) -> str | None:
    if not candidate:
        return None
    candidate = candidate.strip()
    if not candidate or candidate.startswith(("data:", "javascript:", "blob:", "about:", "#")):
        return None
    try:
        absolute = urljoin(base, candidate)
        parts = urlsplit(absolute)
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    host = parts.hostname.lower()
    if is_blocked_hostname(host):
        return None
    try:
        import ipaddress

        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        if is_blocked_ip(host):
            return None
    return absolute.split("#", 1)[0]


def _ext_of(url: str) -> str | None:
    path = urlsplit(url).path
    if "." not in path.rsplit("/", 1)[-1]:
        return None
    ext = path.rsplit(".", 1)[-1].lower()
    return ext if ext in EXTENSION_MIME else None


def _type_for_ext(ext: str | None) -> ResourceType:
    if not ext:
        return ResourceType.UNKNOWN
    if ext in _IMAGE_EXT:
        return ResourceType.IMAGE
    if ext in _VIDEO_EXT:
        return ResourceType.VIDEO
    if ext in _AUDIO_EXT:
        return ResourceType.AUDIO
    if ext == "pdf":
        return ResourceType.PDF
    if ext in _DOC_EXT:
        return ResourceType.DOCUMENT
    if ext in _ARCHIVE_EXT:
        return ResourceType.ARCHIVE
    return ResourceType.UNKNOWN


def _attr(tag: Tag, name: str) -> str | None:
    value = tag.get(name)
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value) if value is not None else None


def parse_page(html: str, base_url: str, *, max_resources: int = 300) -> PageInfo:
    soup = BeautifulSoup(html, "html.parser")
    info = PageInfo()

    base_tag = soup.find("base", href=True)
    if isinstance(base_tag, Tag):
        base_href = _absolute(base_url, _attr(base_tag, "href"))
        if base_href:
            base_url = base_href

    # --- metadata ------------------------------------------------------
    meta: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        if not isinstance(tag, Tag):
            continue
        key = (_attr(tag, "property") or _attr(tag, "name") or _attr(tag, "itemprop") or "").lower()
        content = _attr(tag, "content")
        if key and content and key not in meta:
            meta[key] = content.strip()[:1000]
    title_tag = soup.find("title")
    info.title = _text(
        meta.get("og:title")
        or meta.get("twitter:title")
        or (title_tag.get_text() if title_tag else None)
    )
    info.description = _text(
        meta.get("og:description") or meta.get("twitter:description") or meta.get("description")
    )
    info.site_name = _text(meta.get("og:site_name"))
    canonical_tag = soup.find(
        "link",
        rel=lambda v: (
            bool(v) and "canonical" in [x.lower() for x in (v if isinstance(v, list) else [v])]
        ),
    )
    if isinstance(canonical_tag, Tag):
        info.canonical = _absolute(base_url, _attr(canonical_tag, "href"))
    info.image = _absolute(
        base_url,
        meta.get("og:image")
        or meta.get("og:image:url")
        or meta.get("twitter:image")
        or meta.get("twitter:image:src"),
    )
    info.metadata = {
        "open_graph": {k: v for k, v in meta.items() if k.startswith("og:")},
        "twitter": {k: v for k, v in meta.items() if k.startswith("twitter:")},
        "standard": {
            k: meta[k]
            for k in ("description", "author", "keywords", "generator", "theme-color", "robots")
            if k in meta
        },
    }

    for tag in soup.find_all("link", rel=True):
        if not isinstance(tag, Tag):
            continue
        rels = tag.get("rel")
        rel_list = [str(r).lower() for r in (rels if isinstance(rels, list) else [rels])]
        if any("icon" in r for r in rel_list):
            href = _absolute(base_url, _attr(tag, "href"))
            if href and href not in info.favicons:
                info.favicons.append(href)

    # --- resources -----------------------------------------------------
    seen: set[str] = set()

    def add(
        res_type: ResourceType,
        url: str | None,
        *,
        source: str,
        title: str | None = None,
        mime: str | None = None,
        thumbnail: str | None = None,
    ) -> None:
        if not url or url in seen:
            return
        if len(info.resources) >= max_resources:
            info.truncated = True
            return
        ext = _ext_of(url)
        mime = normalize_mime(mime) or mime_for_extension(ext)
        if res_type == ResourceType.UNKNOWN:
            res_type = resource_type_for_mime(mime) if mime else _type_for_ext(ext)
        if res_type == ResourceType.UNKNOWN:
            return
        seen.add(url)
        info.resources.append(
            FoundResource(
                type=res_type,
                url=url,
                title=_text(title),
                mime_type=mime,
                thumbnail=thumbnail,
                source=source,
            )
        )

    if info.image:
        add(ResourceType.IMAGE, info.image, source="og", title=info.title)

    for tag in soup.find_all("img"):
        if not isinstance(tag, Tag):
            continue
        width, height = _attr(tag, "width"), _attr(tag, "height")
        if _is_tiny(width) or _is_tiny(height):
            continue
        for candidate in _image_candidates(tag):
            add(
                ResourceType.IMAGE,
                _absolute(base_url, candidate),
                source="img",
                title=_attr(tag, "alt") or _attr(tag, "title"),
            )

    for tag in soup.find_all("picture"):
        if not isinstance(tag, Tag):
            continue
        for src in tag.find_all("source"):
            if isinstance(src, Tag):
                for candidate in _srcset(_attr(src, "srcset")):
                    add(
                        ResourceType.IMAGE,
                        _absolute(base_url, candidate),
                        source="source",
                        mime=_attr(src, "type"),
                    )

    for kind, res_type in (("video", ResourceType.VIDEO), ("audio", ResourceType.AUDIO)):
        for tag in soup.find_all(kind):
            if not isinstance(tag, Tag):
                continue
            poster = _absolute(base_url, _attr(tag, "poster")) if kind == "video" else None
            add(
                res_type,
                _absolute(base_url, _attr(tag, "src")),
                source=kind,
                title=_attr(tag, "title"),
                thumbnail=poster,
            )
            for src in tag.find_all("source"):
                if isinstance(src, Tag):
                    add(
                        res_type,
                        _absolute(base_url, _attr(src, "src")),
                        source="source",
                        mime=_attr(src, "type"),
                        thumbnail=poster,
                    )
            if poster:
                add(ResourceType.IMAGE, poster, source="video", title=_attr(tag, "title"))

    for tag in soup.find_all("a", href=True):
        if not isinstance(tag, Tag):
            continue
        href = _absolute(base_url, _attr(tag, "href"))
        if not href:
            continue
        ext = _ext_of(href)
        if ext in _LINK_EXT:
            add(
                _type_for_ext(ext),
                href,
                source="a",
                title=tag.get_text(" ", strip=True) or _attr(tag, "title"),
            )

    for tag in soup.find_all("meta"):
        if not isinstance(tag, Tag):
            continue
        key = (_attr(tag, "property") or _attr(tag, "name") or "").lower()
        content = _absolute(base_url, _attr(tag, "content"))
        if not content:
            continue
        if key in {"og:video", "og:video:url", "og:video:secure_url", "twitter:player:stream"}:
            add(ResourceType.VIDEO, content, source="og", title=info.title, thumbnail=info.image)
        elif key in {"og:audio", "og:audio:url", "og:audio:secure_url"}:
            add(ResourceType.AUDIO, content, source="og", title=info.title)
        elif key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
            add(ResourceType.IMAGE, content, source="og", title=info.title)

    for script in soup.find_all("script", type=lambda v: bool(v) and "ld+json" in str(v).lower()):
        if not isinstance(script, Tag):
            continue
        raw = script.get_text() or ""
        if len(raw) > 200_000:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue
        for item in _walk_jsonld(data, depth=0):
            add(
                ResourceType.VIDEO,
                _absolute(base_url, item.get("contentUrl")),
                source="json-ld",
                title=_text(item.get("name")),
                thumbnail=_absolute(base_url, _text(item.get("thumbnailUrl"))),
            )
            for k in ("image", "thumbnailUrl", "logo"):
                v = item.get(k)
                if isinstance(v, dict):
                    v = v.get("url")
                if isinstance(v, list):
                    v = v[0] if v else None
                if isinstance(v, str):
                    add(
                        ResourceType.IMAGE,
                        _absolute(base_url, v),
                        source="json-ld",
                        title=_text(item.get("name")),
                    )

    return info


def _walk_jsonld(node: Any, depth: int) -> list[dict[str, Any]]:
    if depth > 6:
        return []
    out: list[dict[str, Any]] = []
    if isinstance(node, dict):
        if node.get("@type") in {
            "VideoObject",
            "AudioObject",
            "ImageObject",
            "Article",
            "NewsArticle",
            "Product",
            "WebPage",
            "Organization",
        }:
            out.append(node)
        for v in node.values():
            out.extend(_walk_jsonld(v, depth + 1))
    elif isinstance(node, list):
        for v in node[:50]:
            out.extend(_walk_jsonld(v, depth + 1))
    return out


def _is_tiny(value: str | None) -> bool:
    if not value:
        return False
    try:
        return int(str(value).rstrip("px")) <= 2
    except ValueError:
        return False


def _image_candidates(tag: Tag) -> list[str]:
    out: list[str] = []
    for attr in ("src", "data-src", "data-original", "data-lazy-src"):
        v = _attr(tag, attr)
        if v:
            out.append(v)
    for attr in ("srcset", "data-srcset"):
        out.extend(_srcset(_attr(tag, attr)))
    return out


def _srcset(value: str | None) -> list[str]:
    if not value:
        return []
    return [m.group(1) for m in _SRCSET_RE.finditer(value) if m.group(1)][:10]
