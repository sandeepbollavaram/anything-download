"""Ephemeral local filesystem storage.

Layout under ``AD_STORAGE_DIR``::

    jobs/<job_id>/<result file>      results served to users (TTL bound)
    uploads/<upload_id>/<file>       user uploads awaiting processing (TTL bound)
    work/<job_id>/                   scratch space, removed when a job finishes

Identifiers are strictly validated so paths can never escape the root. The
storage layer is intentionally simple; an S3-compatible backend can implement
the same small surface (see docs/architecture.md).
"""

from __future__ import annotations

import asyncio
import re
import shutil
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

from anything_download.config import Settings, get_settings
from anything_download.logging import get_logger

log = get_logger(__name__)

_ID_RE = re.compile(r"^[a-f0-9]{32}$")


def new_id() -> str:
    return uuid.uuid4().hex


def validate_id(value: str) -> str:
    if not isinstance(value, str) or not _ID_RE.match(value):
        raise ValueError("invalid identifier")
    return value


class LocalStorage:
    def __init__(self, root: Path | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.root = (root or self.settings.storage_dir).resolve()
        self.jobs_root = self.root / "jobs"
        self.uploads_root = self.root / "uploads"
        self.work_root = self.root / "work"

    def ensure_dirs(self) -> None:
        for path in (self.jobs_root, self.uploads_root, self.work_root):
            path.mkdir(parents=True, exist_ok=True)

    # -- path helpers -----------------------------------------------------
    def job_dir(self, job_id: str) -> Path:
        return self.jobs_root / validate_id(job_id)

    def upload_dir(self, upload_id: str) -> Path:
        return self.uploads_root / validate_id(upload_id)

    def work_dir(self, job_id: str) -> Path:
        return self.work_root / validate_id(job_id)

    def create_work_dir(self, job_id: str) -> Path:
        path = self.work_dir(job_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_job_dir(self, job_id: str) -> Path:
        path = self.job_dir(job_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def create_upload_dir(self, upload_id: str) -> Path:
        path = self.upload_dir(upload_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolve_within(self, base: Path, name: str) -> Path:
        """Join ``name`` onto ``base`` and guarantee the result stays inside ``base``.

        Backslashes are refused on every platform, not just Windows: on Linux a
        name like ``..<backslash>x`` is a literal filename that stays inside
        ``base``, but the same stored name would traverse if the tree were ever
        read on Windows. Callers pass ``sanitize_filename`` output, which never
        contains one.
        """
        if "\\" in name or "\0" in name:
            raise ValueError("path contains a backslash or NUL byte")
        candidate = (base / name).resolve()
        base_resolved = base.resolve()
        if candidate != base_resolved and base_resolved not in candidate.parents:
            raise ValueError("path escapes storage directory")
        return candidate

    # -- lifecycle ---------------------------------------------------------
    def delete_tree_sync(self, path: Path) -> bool:
        """Remove a directory tree. Returns True if something was removed."""
        resolved = path.resolve()
        if self.root not in resolved.parents:
            raise ValueError("refusing to delete outside storage root")
        if not resolved.exists():
            return False
        shutil.rmtree(resolved, ignore_errors=True)
        if resolved.exists():  # pragma: no cover - platform specific
            log.warning("storage.delete_incomplete", path=str(resolved))
            return False
        return True

    async def delete_tree(self, path: Path) -> bool:
        return await asyncio.to_thread(self.delete_tree_sync, path)

    async def delete_job(self, job_id: str) -> bool:
        removed = await self.delete_tree(self.job_dir(job_id))
        await self.delete_tree(self.work_dir(job_id))
        return removed

    async def delete_upload(self, upload_id: str) -> bool:
        return await self.delete_tree(self.upload_dir(upload_id))

    def list_ids(self, base: Path) -> list[str]:
        if not base.exists():
            return []
        return [p.name for p in base.iterdir() if p.is_dir() and _ID_RE.match(p.name)]

    def dir_size(self, path: Path) -> int:
        total = 0
        if not path.exists():
            return 0
        for child in path.rglob("*"):
            if child.is_file():
                total += child.stat().st_size
        return total

    # -- streaming write ------------------------------------------------------
    async def write_stream(
        self,
        destination: Path,
        chunks: AsyncIterator[bytes],
        *,
        max_bytes: int,
        on_progress: object | None = None,
    ) -> int:
        """Write an async byte stream to ``destination``, enforcing ``max_bytes``.

        Raises :class:`ValueError` (``"too large"``) when the limit is exceeded; the
        partial file is removed.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        tmp = destination.with_suffix(destination.suffix + ".part")
        try:
            with tmp.open("wb") as fh:
                async for chunk in chunks:
                    written += len(chunk)
                    if written > max_bytes:
                        raise ValueError("too large")
                    fh.write(chunk)
                    if callable(on_progress):
                        on_progress(written)
            tmp.replace(destination)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return written
