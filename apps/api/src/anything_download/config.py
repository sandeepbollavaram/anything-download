"""Application configuration.

Every environment-specific value is read from environment variables (or a
``.env`` file in development). See ``.env.example`` at the repository root for
documentation of each variable.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "console"
    public_url: str = "http://localhost:3000"
    """Public origin of the web app (used for CORS and absolute links)."""
    api_root_path: str = ""

    # --- Infrastructure ------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    storage_dir: Path = Path("./data")
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    # --- Limits --------------------------------------------------------------
    max_file_size_mb: int = 500
    """Maximum size of a remote file we will download (bytes are streamed)."""
    max_upload_size_mb: int = 200
    max_job_duration_seconds: int = 600
    max_video_duration_seconds: int = 7200
    """Refuse to process media longer than this (unknown duration is allowed)."""
    max_concurrent_jobs: int = 2
    """Concurrent jobs per worker process."""
    max_queue_depth: int = 200
    max_request_body_kb: int = 256
    """Largest JSON/form body accepted outside the streaming upload endpoint."""
    ffmpeg_threads: int = 2
    """Threads per ffmpeg process (0 = ffmpeg default, i.e. every core)."""

    # --- Storage pressure -----------------------------------------------------
    min_free_disk_mb: int = 2048
    """Refuse new uploads and jobs once the storage filesystem has less free space than
    this. Keep it above max_file_size_mb x max_concurrent_jobs x worker count so work
    already admitted can still finish."""
    max_storage_mb: int = 0
    """Quota on the total size of AD_STORAGE_DIR (0 = no quota, free-space floor only)."""
    max_url_length: int = 2048
    max_webpage_bytes: int = 3 * 1024 * 1024
    max_webpage_resources: int = 300
    max_pdf_pages: int = 500
    max_image_pixels: int = 50_000_000
    max_redirects: int = 5
    http_connect_timeout_seconds: float = 8.0
    http_read_timeout_seconds: float = 20.0
    subprocess_grace_seconds: float = 5.0

    # --- Retention -----------------------------------------------------------
    result_ttl_minutes: int = 30
    upload_ttl_minutes: int = 30
    job_record_ttl_minutes: int = 120
    cleanup_interval_seconds: int = 60

    # --- Rate limiting -------------------------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_analyze_per_minute: int = 30
    rate_limit_jobs_per_minute: int = 20
    rate_limit_uploads_per_minute: int = 10
    rate_limit_general_per_minute: int = 240
    trust_proxy_headers: bool = False
    """Trust ``X-Forwarded-For`` from the immediate upstream (only enable behind a proxy)."""

    # --- Feature flags -------------------------------------------------------
    enable_platform_extractors: bool = True
    enable_browser_tools: bool = False
    """URL→PDF and screenshot tools require Playwright + Chromium in the worker image."""
    enable_docs: bool = True
    """Serve OpenAPI docs at /api/v1/docs."""

    # --- Networking ----------------------------------------------------------
    user_agent: str = (
        "AnythingDownload/0.1 (+https://github.com/sandeepbollavaram/anything-download)"
    )
    allow_private_targets: bool = False
    """Testing only: allows requests to loopback/private addresses. Never enable in production."""

    @field_validator("storage_dir", mode="after")
    @classmethod
    def _absolute_storage_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @model_validator(mode="after")
    def _refuse_unsafe_production(self) -> Settings:
        if self.env == "production" and self.allow_private_targets:
            raise ValueError("AD_ALLOW_PRIVATE_TARGETS cannot be enabled when AD_ENV=production.")
        if self.env == "production":
            explicit = os.environ.get("AD_ENABLE_DOCS", "").strip().lower()
            if explicit not in {"1", "true", "yes", "on"}:
                self.enable_docs = False
        return self

    # Derived values ---------------------------------------------------------
    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def min_free_disk_bytes(self) -> int:
        return self.min_free_disk_mb * 1024 * 1024

    @property
    def max_storage_bytes(self) -> int:
        return self.max_storage_mb * 1024 * 1024

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def result_ttl_seconds(self) -> int:
        return self.result_ttl_minutes * 60

    @property
    def upload_ttl_seconds(self) -> int:
        return self.upload_ttl_minutes * 60

    @property
    def job_record_ttl_seconds(self) -> int:
        return self.job_record_ttl_minutes * 60

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.public_url.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Testing helper: drop the cached settings so env changes are picked up."""
    get_settings.cache_clear()
