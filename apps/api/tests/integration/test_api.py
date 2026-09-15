"""HTTP-level tests against the FastAPI app with fakeredis and a fake web."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient
from PIL import Image

from anything_download.config import Settings
from anything_download.workers.worker import Worker
from tests.conftest import FakeWeb, requires_ffmpeg


@pytest.mark.integration
async def test_health_and_tools(api_client: AsyncClient) -> None:
    health = await api_client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    tools = await api_client.get("/api/v1/tools")
    assert tools.status_code == 200
    ids = {t["id"] for t in tools.json()["tools"]}
    for required in (
        "video-downloader",
        "image-compressor",
        "pdf-merger",
        "audio-converter",
        "url-analyzer",
        "qr-generator",
    ):
        assert required in ids


@pytest.mark.integration
async def test_analyze_direct_pdf(api_client: AsyncClient, fake_web: FakeWeb) -> None:
    fake_web.add(
        "https://files.example/doc.pdf",
        b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n",
        content_type="application/pdf",
    )
    response = await api_client.post(
        "/api/v1/analyze", json={"url": "https://files.example/doc.pdf"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["resource_type"] == "PDF"
    assert body["source_kind"] == "direct"
    assert "pdf-downloader" in body["tools"]
    assert "DOWNLOAD" in body["capabilities"]


@pytest.mark.integration
async def test_analyze_webpage_filters_empty_finders(
    api_client: AsyncClient, fake_web: FakeWeb
) -> None:
    html = (
        "<!doctype html><html><head><title>Demo</title></head><body><p>no media</p></body></html>"
    )
    fake_web.add("https://site.example/", html, content_type="text/html")
    response = await api_client.post("/api/v1/analyze", json={"url": "https://site.example/"})
    assert response.status_code == 200
    body = response.json()
    assert body["resource_type"] == "WEBPAGE"
    assert "url-analyzer" in body["tools"]
    assert "website-image-gallery" not in body["tools"]
    assert "website-video-finder" not in body["tools"]


@pytest.mark.integration
async def test_analyze_blocked_and_bad_scheme(api_client: AsyncClient) -> None:
    js = await api_client.post("/api/v1/analyze", json={"url": "javascript:alert(1)"})
    assert js.status_code == 400
    assert js.json()["error"]["code"] == "UNSUPPORTED_SCHEME"

    loopback = await api_client.post("/api/v1/analyze", json={"url": "http://127.0.0.1/secret"})
    assert loopback.status_code == 400
    assert loopback.json()["error"]["code"] == "BLOCKED_TARGET"


@pytest.mark.integration
async def test_analyze_unreachable_is_structured(
    api_client: AsyncClient, fake_web: FakeWeb
) -> None:
    fake_web.add("https://gone.example/x", b"missing", status=404, content_type="text/plain")
    response = await api_client.post("/api/v1/analyze", json={"url": "https://gone.example/x"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert body["reason"]["code"] == "SOURCE_NOT_FOUND"
    assert body["tools"] == []


@pytest.mark.integration
async def test_upload_and_image_job(
    api_client: AsyncClient,
    settings: Settings,
    store,
    storage,
) -> None:
    buf = io.BytesIO()
    Image.new("RGB", (48, 32), (20, 180, 80)).save(buf, format="PNG")
    png = buf.getvalue()

    uploaded = await api_client.post(
        "/api/v1/uploads",
        content=png,
        headers={"X-File-Name": "photo.png", "Content-Type": "application/octet-stream"},
    )
    assert uploaded.status_code == 201
    upload = uploaded.json()
    assert upload["resource_type"] == "IMAGE"
    assert "image-compressor" in upload["tools"]

    created = await api_client.post(
        "/api/v1/jobs",
        json={
            "tool": "image-to-webp",
            "input": {"kind": "upload", "upload_id": upload["id"]},
            "options": {"quality": 80},
        },
    )
    assert created.status_code == 202
    job_id = created.json()["id"]

    worker = Worker(store, storage, settings, worker_id="test-worker")
    await worker.process_one(job_id)

    viewed = await api_client.get(f"/api/v1/jobs/{job_id}")
    assert viewed.status_code == 200
    body = viewed.json()
    assert body["status"] == "COMPLETED"
    assert body["result"]["file"]["mime_type"] == "image/webp"
    assert body["result_url"] == f"/api/v1/jobs/{job_id}/result"

    download = await api_client.get(f"/api/v1/jobs/{job_id}/result")
    assert download.status_code == 200
    assert download.content[:4] == b"RIFF"
    assert b"WEBP" in download.content[:16]


@pytest.mark.integration
async def test_qr_generator_job(
    api_client: AsyncClient, settings: Settings, store, storage
) -> None:
    created = await api_client.post(
        "/api/v1/jobs",
        json={
            "tool": "qr-generator",
            "input": {"kind": "text", "text": "https://example.com/ok"},
            "options": {"format": "png", "scale": 4},
        },
    )
    assert created.status_code == 202
    job_id = created.json()["id"]
    worker = Worker(store, storage, settings, worker_id="qr-worker")
    await worker.process_one(job_id)
    viewed = await api_client.get(f"/api/v1/jobs/{job_id}")
    assert viewed.json()["status"] == "COMPLETED"
    file_resp = await api_client.get(f"/api/v1/jobs/{job_id}/result")
    assert file_resp.status_code == 200
    assert file_resp.content[:8] == b"\x89PNG\r\n\x1a\n"


@pytest.mark.integration
async def test_job_unknown_tool(api_client: AsyncClient) -> None:
    response = await api_client.post(
        "/api/v1/jobs",
        json={"tool": "not-a-real-tool", "input": {"kind": "text", "text": "x"}},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "TOOL_NOT_FOUND"


@pytest.mark.integration
async def test_delete_job_removes_file(
    api_client: AsyncClient, settings: Settings, store, storage
) -> None:
    created = await api_client.post(
        "/api/v1/jobs",
        json={
            "tool": "qr-generator",
            "input": {"kind": "text", "text": "delete-me"},
            "options": {},
        },
    )
    job_id = created.json()["id"]
    await Worker(store, storage, settings, worker_id="del").process_one(job_id)
    assert (await api_client.get(f"/api/v1/jobs/{job_id}/result")).status_code == 200
    deleted = await api_client.delete(f"/api/v1/jobs/{job_id}")
    assert deleted.status_code == 204
    missing = await api_client.get(f"/api/v1/jobs/{job_id}")
    assert missing.status_code == 404


@pytest.mark.integration
async def test_rate_limit_analyze(
    api_client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The limiter uses fixed one-minute windows; pin the clock so the three requests
    # cannot straddle a window boundary (that made this test fail intermittently).
    from anything_download.api import ratelimit

    monkeypatch.setattr(ratelimit.time, "time", lambda: 1_800_000_030.0)
    settings.rate_limit_analyze_per_minute = 2
    first = await api_client.post("/api/v1/analyze", json={"url": "javascript:x"})
    second = await api_client.post("/api/v1/analyze", json={"url": "javascript:y"})
    third = await api_client.post("/api/v1/analyze", json={"url": "javascript:z"})
    assert first.status_code == 400
    assert second.status_code == 400
    assert third.status_code == 429
    assert third.headers.get("Retry-After")
    assert third.json()["error"]["code"] == "RATE_LIMITED"


@pytest.mark.integration
@requires_ffmpeg
async def test_video_metadata_job(
    api_client: AsyncClient, settings: Settings, store, storage, tmp_path
) -> None:
    import shutil
    import subprocess

    src = tmp_path / "clip.mp4"
    ffmpeg = shutil.which(settings.ffmpeg_bin)
    assert ffmpeg
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x120:d=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(src),
        ],
        check=True,
        capture_output=True,
    )
    uploaded = await api_client.post(
        "/api/v1/uploads",
        content=src.read_bytes(),
        headers={"X-File-Name": "clip.mp4"},
    )
    assert uploaded.status_code == 201
    job = await api_client.post(
        "/api/v1/jobs",
        json={
            "tool": "video-metadata",
            "input": {"kind": "upload", "upload_id": uploaded.json()["id"]},
            "options": {},
        },
    )
    job_id = job.json()["id"]
    await Worker(store, storage, settings, worker_id="ff").process_one(job_id)
    viewed = await api_client.get(f"/api/v1/jobs/{job_id}")
    body = viewed.json()
    assert body["status"] == "COMPLETED"
    streams = body["result"]["data"]["streams"]
    assert any(s.get("codec_type") == "video" for s in streams)


@pytest.mark.integration
async def test_ready_reports_redis(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["redis"] is True


@pytest.mark.asyncio
async def test_job_rejects_upload_of_unaccepted_type_before_queueing(
    api_client: AsyncClient, redis
) -> None:
    """A tool given a file type it cannot process fails at creation, not in the worker."""
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (0, 0, 0)).save(buf, format="PNG")
    uploaded = await api_client.post(
        "/api/v1/uploads",
        content=buf.getvalue(),
        headers={"X-File-Name": "not-a.pdf.png", "Content-Type": "application/octet-stream"},
    )
    assert uploaded.status_code == 201
    upload = uploaded.json()
    assert "pdf-compressor" not in upload["tools"]

    created = await api_client.post(
        "/api/v1/jobs",
        json={"tool": "pdf-compressor", "input": {"kind": "upload", "upload_id": upload["id"]}},
    )
    assert created.status_code == 415
    assert created.json()["error"]["code"] == "FILE_TYPE_UNSUPPORTED"

    from anything_download.jobs.store import QUEUE_KEY

    assert await redis.llen(QUEUE_KEY) == 0, "a job that cannot succeed must not be queued"


@pytest.mark.asyncio
async def test_limits_endpoint_matches_enforced_settings(
    api_client: AsyncClient, settings: Settings
) -> None:
    response = await api_client.get("/api/v1/limits")
    assert response.status_code == 200
    body = response.json()
    assert body["max_upload_bytes"] == settings.max_upload_size_bytes
    assert body["max_file_bytes"] == settings.max_file_size_bytes
    assert body["max_url_length"] == settings.max_url_length
    assert body["max_text_chars"] == 10_000
    assert body["result_ttl_seconds"] == settings.result_ttl_seconds
    assert "public" in response.headers["cache-control"]
    # The published text limit is the one enforced.
    too_long = "x" * (body["max_text_chars"] + 1)
    created = await api_client.post(
        "/api/v1/jobs", json={"tool": "qr-generator", "input": {"kind": "text", "text": too_long}}
    )
    assert created.status_code == 422
