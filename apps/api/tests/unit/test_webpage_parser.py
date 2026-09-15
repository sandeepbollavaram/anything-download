from pathlib import Path

from anything_download.domain import ResourceType
from anything_download.extractors.generic_webpage import parse_page

FIXTURE = Path(__file__).parent.parent / "fixtures" / "page.html"


def test_parse_page_metadata() -> None:
    page = parse_page(FIXTURE.read_text(encoding="utf-8"), "https://site.example/page")
    assert page.title == "OG Title"
    assert page.description == "A page used by tests."
    assert page.canonical == "https://site.example/page"
    assert page.image == "https://site.example/images/og.jpg"
    assert "https://site.example/favicon.png" in page.favicons
    assert "https://site.example/apple-touch-icon.png" in page.favicons
    assert page.metadata["open_graph"]["og:title"] == "OG Title"


def test_parse_page_resources() -> None:
    page = parse_page(FIXTURE.read_text(encoding="utf-8"), "https://site.example/page")
    urls = {r.url for r in page.resources}
    # images
    assert "https://site.example/images/a.jpg" in urls
    assert "https://cdn.example.org/lazy.webp" in urls
    assert "https://cdn.example.org/lazy-2x.webp" in urls
    assert "https://site.example/images/pic.avif" in urls
    assert "https://site.example/images/poster.png" in urls
    assert "https://cdn.example.org/tw.png" in urls
    # media
    assert "https://site.example/media/clip.webm" in urls
    assert "https://cdn.example.org/media/clip.mp4" in urls
    assert "https://cdn.example.org/ld.webm" in urls
    assert "https://site.example/media/track.mp3" in urls
    # documents
    assert "https://site.example/docs/report.pdf" in urls
    assert "https://site.example/docs/archive.zip" in urls
    # excluded
    assert not any(u.startswith("data:") for u in urls)
    assert "https://site.example/pixel.gif" not in urls
    assert "https://site.example/about" not in urls
    assert not any(
        "127.0.0.1" in u or "localhost" in u or "metadata.google.internal" in u for u in urls
    )

    counts = page.counts()
    assert counts["IMAGE"] >= 6
    assert counts["VIDEO"] == 3
    assert counts["AUDIO"] == 1
    assert counts["PDF"] == 1
    assert counts["ARCHIVE"] == 1

    pdf = next(r for r in page.resources if r.type == ResourceType.PDF)
    assert pdf.title == "Annual report"
    assert pdf.mime_type == "application/pdf"


def test_parse_page_limit() -> None:
    html = "<html><body>" + "".join(f'<img src="/i{i}.png">' for i in range(50)) + "</body></html>"
    page = parse_page(html, "https://site.example/", max_resources=10)
    assert len(page.resources) == 10
    assert page.truncated


def test_parse_page_base_tag() -> None:
    html = '<html><head><base href="https://cdn.example.org/assets/"></head><body><img src="x.png"></body></html>'
    page = parse_page(html, "https://site.example/")
    assert page.resources[0].url == "https://cdn.example.org/assets/x.png"


def test_parse_garbage_does_not_crash() -> None:
    page = parse_page("<<<>>> not html at all \x00\x01", "https://site.example/")
    assert page.resources == []
    assert page.title is None
