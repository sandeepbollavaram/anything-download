"""Job worker: pulls jobs from Redis and runs them with bounded concurrency."""

from __future__ import annotations

import asyncio
import contextlib
import signal
import socket
import uuid

import redis.asyncio as aioredis

from anything_download.config import Settings, get_settings
from anything_download.domain import JobStatus
from anything_download.jobs.models import utcnow
from anything_download.jobs.runner import JobRunner
from anything_download.jobs.store import JobStore
from anything_download.logging import configure_logging, get_logger
from anything_download.storage.local import LocalStorage
from anything_download.tools.registry import load_all

log = get_logger(__name__)

HEARTBEAT_SECONDS = 10
HEARTBEAT_TTL = 45


class Worker:
    def __init__(
        self,
        store: JobStore,
        storage: LocalStorage,
        settings: Settings,
        *,
        worker_id: str | None = None,
    ) -> None:
        self.store = store
        self.storage = storage
        self.settings = settings
        self.worker_id = worker_id or f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.runner = JobRunner(store, storage, settings)
        self._semaphore = asyncio.Semaphore(max(1, settings.max_concurrent_jobs))
        self._tasks: set[asyncio.Task[None]] = set()
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        self._stop.set()

    async def heartbeat_loop(self) -> None:
        cycles = 0
        while not self._stop.is_set():
            try:
                await self.store.heartbeat(self.worker_id, HEARTBEAT_TTL)
                cycles += 1
                if cycles % 3 == 0:
                    await self.store.reap_stale_workers()
            except Exception as exc:  # noqa: BLE001
                log.warning("worker.heartbeat_failed", error=type(exc).__name__)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=HEARTBEAT_SECONDS)

    async def run_forever(self) -> None:
        load_all()
        self.storage.ensure_dirs()
        log.info(
            "worker.started",
            worker_id=self.worker_id,
            concurrency=self.settings.max_concurrent_jobs,
        )
        hb = asyncio.create_task(self.heartbeat_loop())
        try:
            while not self._stop.is_set():
                await self._semaphore.acquire()
                if self._stop.is_set():
                    self._semaphore.release()
                    break
                try:
                    job_id = await self.store.dequeue(self.worker_id, timeout=2)
                except Exception as exc:  # noqa: BLE001
                    self._semaphore.release()
                    log.warning("worker.dequeue_failed", error=type(exc).__name__)
                    await asyncio.sleep(2.0)
                    continue
                if job_id is None:
                    self._semaphore.release()
                    continue
                task = asyncio.create_task(self._process(job_id))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        finally:
            if self._tasks:
                log.info("worker.draining", pending=len(self._tasks))
                await asyncio.gather(*self._tasks, return_exceptions=True)
            self._stop.set()
            hb.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await hb
            log.info("worker.stopped", worker_id=self.worker_id)

    async def process_one(self, job_id: str) -> None:
        """Process a single job id (used by tests and by the main loop)."""
        record = await self.store.get(job_id)
        if record is None:
            log.warning("worker.job_missing", job_id=job_id)
            return
        if record.status != JobStatus.QUEUED:
            log.info("worker.skip_non_queued", job_id=job_id, status=record.status.value)
            return
        if await self.store.is_cancel_requested(job_id):
            await self.store.mark_cancelled(job_id)
            return

        def mutate(r: object) -> None:
            r.started_at = utcnow()  # type: ignore[attr-defined]
            r.worker_id = self.worker_id  # type: ignore[attr-defined]

        running = await self.store.transition(
            job_id, [JobStatus.QUEUED], JobStatus.RUNNING, mutate=mutate
        )
        if running is None:
            return
        await self.runner.run(running)

    async def _process(self, job_id: str) -> None:
        try:
            await self.process_one(job_id)
        except Exception as exc:
            log.exception("worker.process_crashed", job_id=job_id, error=type(exc).__name__)
            from anything_download.errors import ErrorCode, ErrorPayload

            with contextlib.suppress(Exception):
                await self.store.fail(
                    job_id,
                    ErrorPayload(
                        code=ErrorCode.INTERNAL_ERROR,
                        message="The worker crashed while processing this job. Please try again.",
                        retryable=True,
                    ),
                )
        finally:
            with contextlib.suppress(Exception):
                await self.store.ack(self.worker_id, job_id)
            self._semaphore.release()


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_format)
    redis = aioredis.Redis.from_url(settings.redis_url)
    store = JobStore(redis, settings)
    storage = LocalStorage(settings=settings)
    worker = Worker(store, storage, settings)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows lacks add_signal_handler
            loop.add_signal_handler(sig, worker.request_stop)
    try:
        await worker.run_forever()
    finally:
        await redis.aclose()


if __name__ == "__main__":
    asyncio.run(main())
