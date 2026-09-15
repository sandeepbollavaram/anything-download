"""Results are served from the API, which production routes on the site's own origin.

A result file that a browser would execute (SVG, HTML) must never be rendered
inline there: opening a shared result link would run attacker script as the site.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from anything_download.config import Settings
from anything_download.workers.worker import Worker
from tests.conftest import FakeWeb

SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
    "<script>alert(document.domain)</script><rect width='10' height='10'/></svg>"
)


async def _download(
    api_client: AsyncClient,
    fake_web: FakeWeb,
    settings: Settings,
    store,
    storage,
    url: str,
    body: str,
    content_type: str,
    tool: str,
) -> dict:
    fake_web.add(url, body, content_type=content_type)
    created = await api_client.post(
        "/api/v1/jobs", json={"tool": tool, "input": {"kind": "url", "url": url}}
    )
    assert created.status_code == 202, created.text
    job_id = created.json()["id"]
    await Worker(store, storage, settings, worker_id="t").process_one(job_id)
    job = (await api_client.get(f"/api/v1/jobs/{job_id}")).json()
    assert job["status"] == "COMPLETED", job.get("error")
    result = await api_client.get(f"/api/v1/jobs/{job_id}/result")
    assert result.status_code == 200
    return {"job": job, "headers": result.headers}


@pytest.mark.security
@pytest.mark.asyncio
async def test_svg_result_is_never_served_inline(
    api_client: AsyncClient, fake_web: FakeWeb, settings: Settings, store, storage
) -> None:
    got = await _download(
        api_client,
        fake_web,
        settings,
        store,
        storage,
        "https://cdn.example.com/logo.svg",
        SVG,
        "image/svg+xml",
        "image-downloader",
    )
    headers = got["headers"]
    assert headers["content-disposition"].startswith("attachment"), headers["content-disposition"]
    assert headers["x-content-type-options"] == "nosniff"
    assert "sandbox" in headers.get("content-security-policy", "")


@pytest.mark.security
@pytest.mark.asyncio
async def test_html_is_refused_as_a_downloadable_result(
    api_client: AsyncClient, fake_web: FakeWeb, settings: Settings, store, storage
) -> None:
    url = "https://cdn.example.com/page.html"
    fake_web.add(url, "<script>alert(1)</script>", content_type="text/html")
    created = await api_client.post(
        "/api/v1/jobs", json={"tool": "file-downloader", "input": {"kind": "url", "url": url}}
    )
    job_id = created.json()["id"]
    await Worker(store, storage, settings, worker_id="t").process_one(job_id)
    job = (await api_client.get(f"/api/v1/jobs/{job_id}")).json()
    assert job["status"] == "FAILED"
    assert job["error"]["code"] == "SOURCE_INVALID_CONTENT"
    assert (await api_client.get(f"/api/v1/jobs/{job_id}/result")).status_code != 200


@pytest.mark.security
@pytest.mark.asyncio
async def test_raster_result_stays_inline_for_previews_but_is_sandboxed(
    api_client: AsyncClient, settings: Settings, store, storage
) -> None:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 20, 30)).save(buf, format="PNG")
    upload = (
        await api_client.post(
            "/api/v1/uploads",
            content=buf.getvalue(),
            headers={"X-File-Name": "p.png", "Content-Type": "application/octet-stream"},
        )
    ).json()
    created = await api_client.post(
        "/api/v1/jobs",
        json={"tool": "image-to-webp", "input": {"kind": "upload", "upload_id": upload["id"]}},
    )
    job_id = created.json()["id"]
    await Worker(store, storage, settings, worker_id="t").process_one(job_id)
    result = await api_client.get(f"/api/v1/jobs/{job_id}/result")
    assert result.status_code == 200
    assert result.headers["content-disposition"].startswith("inline")
    assert "sandbox" in result.headers["content-security-policy"]
