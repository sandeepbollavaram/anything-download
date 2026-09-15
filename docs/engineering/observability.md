# Observability plan

Goal: know that the service is healthy and bounded without storing user data.
Prefer counters and gauges over logs; never log secrets, credentials, cookies or
full user URLs.

## What exists today

| Signal | Source | Notes |
| --- | --- | --- |
| Liveness | `GET /api/v1/health` | process up |
| Readiness | `GET /api/v1/ready` | `redis`, `storage_writable`, `ffmpeg`, `storage_space` (reported, not gating) |
| Queue depth | `/api/v1/metrics` `queue_depth` | Redis list length |
| Jobs created / completed / failed / expired | `jobs_created_total`, `jobs_completed_total`, `jobs_failed_total`, `jobs_expired_total` | counters in Redis; failures are not broken down by code yet |
| Processing duration | `job_duration_count`, `job_duration_seconds_sum` | average = sum / count |
| Storage | `storage_free_bytes`, `storage_pressure`, `storage_used_bytes` (with a quota) | from the storage guard |
| Cleanup | `cleanup_runs_total`, `cleanup_jobs_expired_total`, `cleanup_uploads_expired_total`, `cleanup_errors_total`, and the `cleanup.cycle` log event | per cycle: expired jobs/uploads, orphans, errors |
| Worker health | `worker:*` heartbeat keys (45 s TTL) | stale workers are reaped |
| Logs | structlog JSON in production | query strings, cookies and tokens redacted; Caddy access log off |

`/api/v1/metrics` is JSON and is **not reachable at the public edge** (Caddy
returns 404); read it from inside the host (see
[deployment](../deployment.md#operational-metrics)). Nothing scrapes, stores or
alerts on these signals yet: there is no monitoring platform in this release.

## Release status of the minimum signals

| Signal | Status |
| --- | --- |
| Request rate | **Not implemented** (gap 1) |
| Error rate | **Not implemented** (gap 1) |
| Job success / failure | Implemented (totals) |
| Failure codes | **Not implemented** (gap 2) |
| Queue depth | Implemented |
| Processing duration | Implemented (sum and count, no histogram) |
| Storage pressure | Implemented |
| Worker health | Heartbeats and reaping exist; no metric or alert (gap 3) |

## Gaps to close (in order)

1. **Request and error rates**: counters by route bucket and status class
   (`requests_total{bucket,class}`), including `429` and `5xx`. Cheapest place:
   the existing request middleware, incrementing Redis counters like the job
   metrics.
2. **Failed jobs by code**: `jobs_failed_total{code}` in `JobStore.fail`, so
   `STORAGE_FULL`, `PROCESSING_TIMEOUT` and `FILE_TOO_LARGE` spikes are visible.
3. **Active jobs and live workers**: gauges derived from processing lists and
   heartbeat keys.
4. **Prometheus exposition**: `/api/v1/metrics` returns JSON; add a text
   exposition endpoint reachable only on the internal network (not routed by
   Caddy) for a scraper.
5. **Host metrics**: CPU, memory and disk of the host and containers via
   node-exporter and cAdvisor (or the hosting provider's agent). Container
   limits are set in `docker-compose.prod.yml`; alert on sustained throttling and
   OOM kills.
6. **External probe**: HTTPS check of `/api/v1/ready` from outside, alerting on
   failure and on certificate expiry.

## Alerts (initial)

| Alert | Condition |
| --- | --- |
| Service down | external `/ready` failing for 2 min |
| Redis down | `ready.checks.redis = false` |
| Disk pressure | `storage_pressure = 1` for 5 min, or host disk > 85 % |
| Queue backing up | `queue_depth` > 150 for 10 min |
| Error rate | 5xx > 2 % of requests over 10 min (after gap 1) |
| Abuse | 429 rate far above baseline (after gap 1) |
| Worker loss | no live worker heartbeat for 2 min (after gap 3) |
| Certificate | expires in < 14 days |

## Data rules

- Metrics carry no URL, filename, IP address or user identifier as a label.
- Logs keep hostnames at most, never full URLs or query strings.
- Retain operational logs for days, not months; they exist for abuse control and
  debugging, not analytics.
