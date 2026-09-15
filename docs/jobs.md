# Jobs

Long-running work is asynchronous.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/jobs` | Enqueue a tool run (`202`) |
| GET | `/api/v1/jobs/{id}` | Status, progress, result metadata |
| POST | `/api/v1/jobs/{id}/cancel` | Cooperative cancel |
| GET | `/api/v1/jobs/{id}/result` | Download the file |
| DELETE | `/api/v1/jobs/{id}` | Delete now |

Job ids are 32-character hex UUIDs.

## States

`QUEUED` → `RUNNING` → `COMPLETED` | `FAILED` | `CANCELLED`

`COMPLETED` → `EXPIRED` when the TTL elapses or the file is gone.

Queued jobs cancel immediately. Running jobs set a cancel flag; the runner
checks it between phases and during FFmpeg.

## Redis keys

All keys are prefixed `ad:`:

- `ad:job:<id>` record JSON
- `ad:queue` list
- `ad:processing:<worker>` in-flight ids
- `ad:worker:<worker>` heartbeat
- `ad:expiry` zset of `job:<id>` / `upload:<id>`
- `ad:metrics:*` counters

Workers that stop heartbeating cause in-flight jobs to fail as retryable.
The cleanup process is the primary reaper; each worker also calls
`reap_stale_workers` on a heartbeat cadence so a dead cleanup process does
not leave jobs `RUNNING` forever. Compose marks `worker` and `cleanup` as
`restart: unless-stopped`. All three of API, worker, and cleanup are
required in production. Without cleanup, expired files linger until a
worker reaps dead jobs or an operator runs the cleaner.

## Progress

`JobProgress.percent` is set only from real signals (bytes read / declared
length, FFmpeg `out_time` / duration). The UI must not invent percentages.

## TTL

`AD_RESULT_TTL_MINUTES` (default 30) governs result files.
`AD_UPLOAD_TTL_MINUTES` governs uploads.
`AD_JOB_RECORD_TTL_MINUTES` governs Redis records.

The cleanup process (`python -m anything_download.workers.cleanup`) expires
due members, deletes files, marks jobs expired, and removes orphan
directories older than their TTL.

## Verification

| Item | Status |
| --- | --- |
| State machine + bounded retries + crash → FAILED | Implemented; unit tested |
| Redis-down / worker-down chaos on a live stack | **NOT VERIFIED** locally unless you run it |
| Multi-replica shared storage | Known limitation (local disk) |
