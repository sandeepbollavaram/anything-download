"""Job records and related API models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from anything_download.domain import JobStatus, ResourceType
from anything_download.errors import ErrorPayload


def utcnow() -> datetime:
    return datetime.now(UTC)


class JobInput(BaseModel):
    """What the job operates on: a URL, an uploaded file, or plain text."""

    kind: Literal["url", "upload", "uploads", "text"]
    url: str | None = Field(default=None, description="Required when kind is 'url'.")
    upload_id: str | None = Field(default=None, description="Required when kind is 'upload'.")
    upload_ids: list[str] | None = Field(
        default=None, description="Required when kind is 'uploads' (e.g. PDF merge)."
    )
    text: str | None = Field(default=None, description="Required when kind is 'text' (e.g. QR).")

    @model_validator(mode="after")
    def _check_shape(self) -> JobInput:
        if self.kind == "url" and not self.url:
            raise ValueError("url is required for kind 'url'")
        if self.kind == "upload" and not self.upload_id:
            raise ValueError("upload_id is required for kind 'upload'")
        if self.kind == "uploads" and not self.upload_ids:
            raise ValueError("upload_ids is required for kind 'uploads'")
        if self.kind == "text" and self.text is None:
            raise ValueError("text is required for kind 'text'")
        return self


class JobProgress(BaseModel):
    phase: str = Field(description="Machine readable phase, e.g. 'downloading', 'processing'.")
    percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Only present when real progress is measurable. Never estimated.",
    )
    message: str | None = None


class ResultFile(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int
    resource_type: ResourceType = ResourceType.UNKNOWN


class JobResult(BaseModel):
    file: ResultFile | None = Field(default=None, description="Downloadable output, if any.")
    data: dict[str, Any] | None = Field(
        default=None, description="Structured output for metadata/finder tools."
    )
    notes: list[str] = Field(
        default_factory=list,
        description="User-facing notes about the result (e.g. metadata was removed).",
    )


class JobRecord(BaseModel):
    id: str
    tool: str
    input: JobInput
    options: dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    expires_at: datetime | None = Field(
        default=None, description="When the result file will be deleted."
    )
    progress: JobProgress | None = None
    result: JobResult | None = None
    error: ErrorPayload | None = None
    worker_id: str | None = None

    def public(self) -> JobView:
        return JobView(
            id=self.id,
            tool=self.tool,
            status=self.status,
            created_at=self.created_at,
            started_at=self.started_at,
            finished_at=self.finished_at,
            expires_at=self.expires_at,
            progress=self.progress,
            result=self.result,
            error=self.error,
            result_url=f"/api/v1/jobs/{self.id}/result"
            if self.status == JobStatus.COMPLETED and self.result and self.result.file
            else None,
        )


class JobView(BaseModel):
    """Public representation of a job (no internal fields, no source URL)."""

    id: str
    tool: str
    status: JobStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    expires_at: datetime | None
    progress: JobProgress | None
    result: JobResult | None
    error: ErrorPayload | None
    result_url: str | None


class JobCreateRequest(BaseModel):
    tool: str = Field(description="Tool identifier, see GET /api/v1/tools.")
    input: JobInput
    options: dict[str, Any] = Field(default_factory=dict)


class UploadRecord(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    resource_type: ResourceType
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


class UploadView(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    resource_type: ResourceType
    expires_at: datetime
    tools: list[str] = Field(description="Tool identifiers applicable to this file.")
