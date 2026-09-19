"""Logs must never keep full user URLs: hostnames at most (see docs/engineering/observability.md)."""

from __future__ import annotations

import pytest

from anything_download.logging import _redact_processor, redact_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://youtu.be/SlRW-qNVKtE", "https://youtu.be"),
        ("https://www.youtube.com/watch?v=abc123&t=42", "https://www.youtube.com"),
        (
            "https://user:pass@example.com:8443/private/file.mp4?sig=x#frag",
            "https://example.com:8443",
        ),
        ("http://example.com", "http://example.com"),
    ],
)
def test_redact_url_keeps_scheme_and_host_only(raw: str, expected: str) -> None:
    assert redact_url(raw) == expected


def test_processor_redacts_url_fields_and_urls_inside_messages() -> None:
    event = {
        "event": "analyze",
        "url": "https://youtu.be/SlRW-qNVKtE",
        "final_url": "https://cdn.example.com/v/123.mp4?token=abc",
        "normalized_url": "https://www.youtube.com/watch?v=abc",
        "message": "yt-dlp failed for https://www.youtube.com/watch?v=abc123 (see https://github.com/yt-dlp/yt-dlp/wiki/FAQ)",
        "api_key": "should-not-appear",
    }
    out = _redact_processor(None, "info", dict(event))
    assert out["url"] == "https://youtu.be"
    assert out["final_url"] == "https://cdn.example.com"
    assert out["normalized_url"] == "https://www.youtube.com"
    assert "abc123" not in out["message"] and "watch?v" not in out["message"]
    assert "https://www.youtube.com" in out["message"]
    assert out["api_key"] == "[REDACTED]"
