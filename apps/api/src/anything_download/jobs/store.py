"""Redis-backed job store and queue.

Keys (all prefixed with ``ad:``)::

    ad:job:<id>            JSON JobRecord (TTL = job_record_ttl)
    ad:job:<id>:cancel     "1" when cancellation was requested
    ad:queue               list of queued job ids (LPUSH / BRPOPLPUSH)
    ad:processing:<worker> ids currently being processed by a worker
    ad:worker:<worker>     heartbeat key (TTL) for stale-worker detection
    ad:expiry              zset: member "job:<id>" | "upload:<id>", score = expiry epoch
    ad:upload:<id>         JSON UploadRecord
    ad:metrics:<name>      counters
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import redis.asyncio as aioredis
from redis.exceptions import WatchError

from anything_download.config import Settings, get_settings
from anything_download.domain import JobStatus
from anything_download.errors import AppError, ErrorCode, ErrorPayload
from anything_download.jobs.models import (
    JobProgress,
    JobRecord,
    JobResult,
    UploadRecord,
    utcnow,
)

PREFIX = "ad:"
QUEUE_KEY = f"{PREFIX}queue"
EXPIRY_KEY = f"{PREFIX}expiry"


def job_key(job_id: str) -> str:
    return f"{PREFIX}job:{job_id}"


def cancel_key(job_id: str) -> str:
    return f"{PREFIX}job:{job_id}:cancel"


def processing_key(worker_id: str) -> str:
    return f"{PREFIX}processing:{worker_id}"


def worker_key(worker_id: str) -> str:
    return f"{PREFIX}worker:{worker_id}"


def upload_key(upload_id: str) -> str:
    return f"{PREFIX}upload:{upload_id}"


def metric_key(name: str) -> str:
    return f"{PREFIX}metrics:{name}"


class JobStore:
    def __init__(self, redis: aioredis.Redis, settings: Settings | None = None) -> None:
        self.redis = redis
        self.settings = settings or get_settings()

    # -- jobs --------------------------------------------------------------
    async def create(self, record: JobRecord) -> JobRecord:
        depth = await self.redis.llen(QUEUE_KEY)
        if depth >= self.settings.max_queue_depth:
            raise AppError(
                ErrorCode.QUEUE_FULL,
                "The service is busy right now. Please try again in a few minutes.",
                retry_after=60,
            )
        pipe = self.redis.pipeline(transaction=True)
        pipe.set(
            job_key(record.id), record.model_dump_json(), ex=self.settings.job_record_ttl_seconds
        )
        pipe.lpush(QUEUE_KEY, record.id)
        pipe.incr(metric_key("jobs_created_total"))
        await pipe.execute()
        return record

    async def get(self, job_id: str) -> JobRecord | None:
        raw = await self.redis.get(job_key(job_id))
        if raw is None:
            return None
        return JobRecord.model_validate_json(raw)

    async def require(self, job_id: str) -> JobRecord:
        record = await self.get(job_id)
        if record is None:
            raise AppError(ErrorCode.JOB_NOT_FOUND, "This job does not exist or has expired.")
        return record

    async def save(self, record: JobRecord) -> None:
        record.updated_at = utcnow()
        await self.redis.set(
            job_key(record.id), record.model_dump_json(), ex=self.settings.job_record_ttl_seconds
        )

    async def transition(
        self,
        job_id: str,
        allowed_from: Iterable[JobStatus],
        to: JobStatus,
        *,
        mutate: object | None = None,
    ) -> JobRecord | None:
        """Atomically move a job between states (optimistic locking via WATCH).

        Returns the updated record, or ``None`` if the job was not in one of
        ``allowed_from`` (e.g. it was cancelled meanwhile).
        """
        allowed = set(allowed_from)
        key = job_key(job_id)
        for _ in range(8):
            async with self.redis.pipeline(transaction=True) as pipe:
                try:
                    await pipe.watch(key)
                    raw = await pipe.get(key)
                    if raw is None:
                        await pipe.unwatch()  # type: ignore[no-untyped-call]
                        return None
                    record = JobRecord.model_validate_json(raw)
                    if record.status not in allowed:
                        await pipe.unwatch()  # type: ignore[no-untyped-call]
                        return None
                    record.status = to
                    record.updated_at = utcnow()
                    if callable(mutate):
                        mutate(record)
                    pipe.multi()  # type: ignore[no-untyped-call]
                    pipe.set(key, record.model_dump_json(), ex=self.settings.job_record_ttl_seconds)
                    if to.is_terminal:
                        pipe.incr(metric_key(f"jobs_{to.value.lower()}_total"))
                    await pipe.execute()
                    return record
                except WatchError:
                    continue
        raise AppError(ErrorCode.INTERNAL_ERROR, "Job state could not be updated. Please retry.")

    async def set_progress(self, job_id: str, progress: JobProgress) -> None:
        record = await self.get(job_id)
        if record is None or record.status != JobStatus.RUNNING:
            return
        record.progress = progress
        await self.save(record)

    async def complete(
        self, job_id: str, result: JobResult, expires_at: datetime | None
    ) -> JobRecord | None:
        def mutate(record: JobRecord) -> None:
            record.result = result
            record.finished_at = utcnow()
            record.expires_at = expires_at
            record.progress = None

        return await self.transition(
            job_id, [JobStatus.RUNNING], JobStatus.COMPLETED, mutate=mutate
        )

    async def fail(self, job_id: str, error: ErrorPayload) -> JobRecord | None:
        def mutate(record: JobRecord) -> None:
            record.error = error
            record.finished_at = utcnow()
            record.progress = None

        return await self.transition(
            job_id, [JobStatus.QUEUED, JobStatus.RUNNING], JobStatus.FAILED, mutate=mutate
        )

    async def request_cancel(self, job_id: str) -> JobRecord:
        record = await self.require(job_id)
        if record.status.is_terminal:
            raise AppError(
                ErrorCode.JOB_NOT_CANCELLABLE,
                f"This job is already {record.status.value.lower()} and cannot be cancelled.",
            )
        await self.redis.set(cancel_key(job_id), "1", ex=self.settings.job_record_ttl_seconds)

        def mutate(r: JobRecord) -> None:
            r.finished_at = utcnow()
            r.progress = None

        # Queued jobs are cancelled immediately; running jobs are cancelled cooperatively by the worker.
        updated = await self.transition(
            job_id, [JobStatus.QUEUED], JobStatus.CANCELLED, mutate=mutate
        )
        if updated is not None:
            await self.redis.lrem(QUEUE_KEY, 0, job_id)
            return updated
        return await self.require(job_id)

    async def is_cancel_requested(self, job_id: str) -> bool:
        return bool(await self.redis.exists(cancel_key(job_id)))

    async def mark_cancelled(self, job_id: str) -> JobRecord | None:
        def mutate(r: JobRecord) -> None:
            r.finished_at = utcnow()
            r.progress = None
            r.result = None

        return await self.transition(
            job_id, [JobStatus.QUEUED, JobStatus.RUNNING], JobStatus.CANCELLED, mutate=mutate
        )

    async def mark_expired(self, job_id: str) -> JobRecord | None:
        def mutate(r: JobRecord) -> None:
            r.result = None

        return await self.transition(
            job_id, [JobStatus.COMPLETED], JobStatus.EXPIRED, mutate=mutate
        )

    async def delete(self, job_id: str) -> None:
        pipe = self.redis.pipeline(transaction=True)
        pipe.delete(job_key(job_id), cancel_key(job_id))
        pipe.lrem(QUEUE_KEY, 0, job_id)
        pipe.zrem(EXPIRY_KEY, f"job:{job_id}")
        await pipe.execute()

    # -- queue --------------------------------------------------------------
    async def queue_depth(self) -> int:
        return int(await self.redis.llen(QUEUE_KEY))

    async def dequeue(self, worker_id: str, timeout: int) -> str | None:
        value = await self.redis.blmove(
            QUEUE_KEY, processing_key(worker_id), timeout, "RIGHT", "LEFT"
        )
        if value is None:
            return None
        job_id = value.decode() if isinstance(value, bytes) else str(value)
        if await self.get(job_id) is None:
            await self.ack(worker_id, job_id)
            return None
        return job_id

    async def ack(self, worker_id: str, job_id: str) -> None:
        await self.redis.lrem(processing_key(worker_id), 0, job_id)

    async def heartbeat(self, worker_id: str, ttl_seconds: int) -> None:
        await self.redis.set(worker_key(worker_id), str(int(time.time())), ex=ttl_seconds)

    async def reap_stale_workers(self) -> list[str]:
        """Fail jobs that were being processed by workers that stopped heartbeating."""
        failed: list[str] = []
        async for key in self.redis.scan_iter(match=f"{PREFIX}processing:*", count=100):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            worker_id = key_str.rsplit(":", 1)[-1]
            if await self.redis.exists(worker_key(worker_id)):
                continue
            ids = await self.redis.lrange(key_str, 0, -1)
            for raw_id in ids:
                job_id = raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id)
                updated = await self.fail(
                    job_id,
                    ErrorPayload(
                        code=ErrorCode.PROCESSING_FAILED,
                        message="The worker processing this job was interrupted. Please try again.",
                        retryable=True,
                    ),
                )
                if updated is not None:
                    failed.append(job_id)
            await self.redis.delete(key_str)
        return failed

    # -- expiry index ------------------------------------------------------
    async def schedule_expiry(self, member: str, expires_at: datetime) -> None:
        await self.redis.zadd(EXPIRY_KEY, {member: expires_at.timestamp()})

    async def unschedule_expiry(self, member: str) -> None:
        await self.redis.zrem(EXPIRY_KEY, member)

    async def due_expiries(self, now: datetime | None = None, limit: int = 200) -> list[str]:
        ts = (now or utcnow()).timestamp()
        raw = await self.redis.zrangebyscore(EXPIRY_KEY, "-inf", ts, start=0, num=limit)
        return [m.decode() if isinstance(m, bytes) else str(m) for m in raw]

    # -- uploads -------------------------------------------------------------
    async def save_upload(self, record: UploadRecord) -> None:
        ttl = max(1, int((record.expires_at - utcnow()).total_seconds()) + 60)
        await self.redis.set(upload_key(record.id), record.model_dump_json(), ex=ttl)
        await self.schedule_expiry(f"upload:{record.id}", record.expires_at)

    async def get_upload(self, upload_id: str) -> UploadRecord | None:
        raw = await self.redis.get(upload_key(upload_id))
        return UploadRecord.model_validate_json(raw) if raw else None

    async def delete_upload(self, upload_id: str) -> None:
        pipe = self.redis.pipeline(transaction=True)
        pipe.delete(upload_key(upload_id))
        pipe.zrem(EXPIRY_KEY, f"upload:{upload_id}")
        await pipe.execute()

    # -- metrics -------------------------------------------------------------
    async def incr_metric(self, name: str, amount: int = 1) -> None:
        await self.redis.incrby(metric_key(name), amount)

    async def observe_duration(self, name: str, seconds: float) -> None:
        pipe = self.redis.pipeline(transaction=False)
        pipe.incrbyfloat(metric_key(f"{name}_seconds_sum"), seconds)
        pipe.incr(metric_key(f"{name}_count"))
        await pipe.execute()

    async def metrics_snapshot(self) -> dict[str, float]:
        out: dict[str, float] = {}
        async for key in self.redis.scan_iter(match=f"{PREFIX}metrics:*", count=100):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            value = await self.redis.get(key_str)
            if value is None:
                continue
            text = value.decode() if isinstance(value, bytes) else str(value)
            try:
                out[key_str.split(":", 2)[-1]] = float(text)
            except ValueError:
                continue
        out["queue_depth"] = float(await self.queue_depth())
        return out

    async def ping(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except Exception:  # noqa: BLE001 - any failure means "not ready"
            return False


def result_expiry(settings: Settings) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=settings.result_ttl_seconds)


def upload_expiry(settings: Settings) -> datetime:
    return datetime.now(UTC) + timedelta(seconds=settings.upload_ttl_seconds)
