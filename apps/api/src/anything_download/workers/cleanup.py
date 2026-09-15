"""Cleanup worker: deletes expired results/uploads and reaps stale workers.

Runs independently of user requests. Each cycle:

1. pops due members from the ``ad:expiry`` index,
2. deletes the files and metadata, marks jobs ``EXPIRED``,
3. scans the storage directories for orphans (no record in Redis, older than the TTL),
4. fails jobs whose worker stopped heartbeating,
5. records success/failure counters for observability.
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path

import redis.asyncio as aioredis

from anything_download.config import Settings, get_settings
from anything_download.domain import JobStatus
from anything_download.jobs.store import JobStore
from anything_download.logging import configure_logging, get_logger
from anything_download.storage.local import LocalStorage

log = get_logger(__name__)


@dataclass
class CleanupReport:
    jobs_expired: int = 0
    uploads_expired: int = 0
    orphans_removed: int = 0
    stale_jobs_failed: int = 0
    errors: int = 0
    missing_files: int = 0
    details: list[str] = field(default_factory=list)


class Cleaner:
    def __init__(self, store: JobStore, storage: LocalStorage, settings: Settings) -> None:
        self.store = store
        self.storage = storage
        self.settings = settings

    async def run_once(self) -> CleanupReport:
        report = CleanupReport()
        await self._expire_due(report)
        await self._remove_orphans(report)
        try:
            failed = await self.store.reap_stale_workers()
            report.stale_jobs_failed = len(failed)
        except Exception as exc:  # noqa: BLE001
            report.errors += 1
            log.warning("cleanup.reap_failed", error=type(exc).__name__)
        with contextlib.suppress(Exception):
            await self.store.incr_metric("cleanup_runs_total")
            if report.errors:
                await self.store.incr_metric("cleanup_errors_total", report.errors)
            await self.store.incr_metric("cleanup_jobs_expired_total", report.jobs_expired)
            await self.store.incr_metric("cleanup_uploads_expired_total", report.uploads_expired)
        log.info(
            "cleanup.cycle",
            jobs_expired=report.jobs_expired,
            uploads_expired=report.uploads_expired,
            orphans=report.orphans_removed,
            stale_failed=report.stale_jobs_failed,
            errors=report.errors,
        )
        return report

    async def _expire_due(self, report: CleanupReport) -> None:
        try:
            members = await self.store.due_expiries()
        except Exception as exc:  # noqa: BLE001
            report.errors += 1
            log.warning("cleanup.expiry_query_failed", error=type(exc).__name__)
            return
        for member in members:
            kind, _, ident = member.partition(":")
            try:
                if kind == "job":
                    removed = await self.storage.delete_job(ident)
                    if not removed:
                        report.missing_files += 1
                    await self.store.mark_expired(ident)
                    await self.store.unschedule_expiry(member)
                    report.jobs_expired += 1
                elif kind == "upload":
                    removed = await self.storage.delete_upload(ident)
                    if not removed:
                        report.missing_files += 1
                    await self.store.delete_upload(ident)
                    report.uploads_expired += 1
                else:
                    await self.store.unschedule_expiry(member)
            except ValueError:
                # Malformed identifier in the index: drop it.
                await self.store.unschedule_expiry(member)
            except Exception as exc:  # noqa: BLE001
                report.errors += 1
                log.warning("cleanup.expire_failed", member=member, error=type(exc).__name__)

    async def _remove_orphans(self, report: CleanupReport) -> None:
        """Delete directories with no live record that are older than their TTL (crash safety)."""
        now = time.time()
        checks: list[tuple[Path, str, int]] = [
            (self.storage.jobs_root, "job", self.settings.result_ttl_seconds),
            (self.storage.uploads_root, "upload", self.settings.upload_ttl_seconds),
            (self.storage.work_root, "work", self.settings.max_job_duration_seconds * 2),
        ]
        for base, kind, ttl in checks:
            for ident in self.storage.list_ids(base):
                path = base / ident
                try:
                    age = now - path.stat().st_mtime
                except OSError:
                    continue
                if age < ttl:
                    continue
                try:
                    if kind == "job":
                        record = await self.store.get(ident)
                        if record is not None:
                            if record.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                                continue
                            if record.status == JobStatus.COMPLETED and (
                                record.result is None or record.result.file is None
                            ):
                                await self.storage.delete_tree(path)
                                report.orphans_removed += 1
                                continue
                            if (
                                record.expires_at is not None
                                and record.expires_at.timestamp() > now
                            ):
                                continue
                            await self.store.mark_expired(ident)
                    elif kind == "upload":
                        if await self.store.get_upload(ident) is not None:
                            continue
                    await self.storage.delete_tree(path)
                    report.orphans_removed += 1
                except Exception as exc:  # noqa: BLE001
                    report.errors += 1
                    log.warning("cleanup.orphan_failed", kind=kind, error=type(exc).__name__)

    async def run_forever(self, stop: asyncio.Event) -> None:
        self.storage.ensure_dirs()
        log.info("cleanup.started", interval=self.settings.cleanup_interval_seconds)
        while not stop.is_set():
            try:
                await self.run_once()
            except Exception as exc:
                log.exception("cleanup.cycle_crashed", error=type(exc).__name__)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self.settings.cleanup_interval_seconds)
        log.info("cleanup.stopped")


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    redis = aioredis.Redis.from_url(settings.redis_url)
    cleaner = Cleaner(JobStore(redis, settings), LocalStorage(settings=settings), settings)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    try:
        await cleaner.run_forever(stop)
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
