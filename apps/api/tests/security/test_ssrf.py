"""SSRF and unsafe-input tests. Never contacts real internal services."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from anything_download.config import Settings
from anything_download.errors import AppError, ErrorCode
from anything_download.security.filenames import sanitize_filename
from anything_download.security.urls import is_blocked_ip, parse_url, validate_and_resolve
from anything_download.storage.local import LocalStorage
from tests.conftest import FakeWeb


@pytest.mark.security
@pytest.mark.parametrize(
    "raw",
    [
        "http://127.0.0.1/",
        "http://0.0.0.0/",
        "http://10.0.0.8/admin",
        "http://192.168.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://localhost/",
        "http://metadata.google.internal/",
        "http://router/",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "http://user:pass@example.com/",
        "http://2130706433/",
        "http://127.1/",
        "http://0x7f.0.0.1/",
        "http://0x7f000001/",
    ],
)
def test_parse_rejects_dangerous_targets(raw: str) -> None:
    with pytest.raises(AppError) as exc:
        parse_url(raw)
    assert exc.value.code in {
        ErrorCode.BLOCKED_TARGET,
        ErrorCode.UNSUPPORTED_SCHEME,
        ErrorCode.INVALID_URL,
    }


@pytest.mark.security
async def test_dns_rebinding_blocked(public_dns, settings: Settings) -> None:
    public_dns("safe.example", "127.0.0.1")
    with pytest.raises(AppError) as exc:
        await validate_and_resolve("https://safe.example/ok", settings)
    assert exc.value.code == ErrorCode.BLOCKED_TARGET


@pytest.mark.security
async def test_redirect_to_private_is_blocked(api_client: AsyncClient, fake_web: FakeWeb) -> None:
    fake_web.redirect("https://open.example/go", "http://169.254.169.254/latest/meta-data/")
    response = await api_client.post("/api/v1/analyze", json={"url": "https://open.example/go"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BLOCKED_TARGET"


@pytest.mark.security
def test_filename_traversal_and_devices() -> None:
    assert ".." not in sanitize_filename("../../etc/passwd")
    assert "/" not in sanitize_filename("a/b/c.txt")
    assert "\\" not in sanitize_filename("a\\b\\c.txt")
    assert sanitize_filename("CON") != "CON"
    assert sanitize_filename("lpt1.pdf").lower().startswith("file-")


@pytest.mark.security
def test_storage_rejects_escape(storage: LocalStorage) -> None:
    base = storage.create_job_dir("a" * 32)
    with pytest.raises(ValueError):
        storage.resolve_within(base, "../outside.txt")
    with pytest.raises(ValueError):
        storage.resolve_within(base, "..\\outside.txt")
    with pytest.raises(ValueError):
        storage.resolve_within(base, "ok.txt\0.png")
    with pytest.raises(ValueError):
        storage.job_dir("../not-an-id")


@pytest.mark.security
def test_ipv4_mapped_and_cgnat_blocked() -> None:
    assert is_blocked_ip("::ffff:10.0.0.1")
    assert is_blocked_ip("100.64.0.1")
    assert is_blocked_ip("192.0.0.192")
    assert not is_blocked_ip("93.184.216.34")


@pytest.mark.security
async def test_oversized_url_rejected(api_client: AsyncClient) -> None:
    huge = "https://example.com/" + ("a" * 5000)
    response = await api_client.post("/api/v1/analyze", json={"url": huge})
    assert response.status_code in {400, 414, 422}
    assert response.json()["error"]["code"] in {"URL_TOO_LONG", "VALIDATION_ERROR"}


@pytest.mark.security
async def test_upload_rejects_html_disguised_as_png(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/uploads",
        content=b"<!doctype html><html><body>nope</body></html>",
        headers={"X-File-Name": "photo.png", "X-File-Type": "image/png"},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "FILE_TYPE_UNSUPPORTED"
