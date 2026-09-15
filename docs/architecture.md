# Architecture

Anything Download is a small monorepo with two runtime applications and one
shared Python package.

```
apps/web     Next.js App Router UI
apps/api     FastAPI process + worker + cleanup
```

There is no PostgreSQL. Persistence that exists is:

- Redis: job records, upload metadata, queue, rate-limit counters, metrics
- Local disk under `AD_STORAGE_DIR`: job results, uploads, scratch files

All stored media has a TTL. The cleanup worker deletes expired files and
marks jobs `EXPIRED`.

## Request path

```
Browser
  -> Next.js (pages, SEO, PWA shell)
  -> rewrite /api/* to FastAPI
  -> analyze | upload | create job
  -> Redis queue
  -> worker
  -> temporary file
  -> GET /jobs/{id}/result
  -> cleanup
```

The homepage does not run expensive work during SSR. Analysis and processing
happen through the API.

## Packages inside the API

| Module | Role |
| --- | --- |
| `security.urls` | Normalize, block schemes/hosts, resolve DNS, reject private IPs |
| `security.filenames` | Safe download names |
| `net.client` | SSRF-hardened HTTP client (IP pinning, manual redirects) |
| `detection.mime` | Extension + magic-byte mapping |
| `analysis.engine` | Central URL analyzer |
| `extractors` | Direct files, generic HTML, platform plugins |
| `tools` | User-facing operations sharing engines |
| `jobs` | State machine, Redis store, runner |
| `storage.local` | Path-safe ephemeral filesystem |
| `media.ffmpeg` | Argument-array FFmpeg/FFprobe |
| `media.browser` | Optional Playwright screenshot / URL→PDF |
| `workers` | Job worker and TTL cleanup |

## Jobs

States: `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`, `EXPIRED`, `CANCELLED`.

HTTP handlers never run FFmpeg or download large files. They enqueue a job
and return `202` with a job id. Progress is published only when it is
measurable (download bytes, FFmpeg `out_time`). Otherwise the UI shows
“Processing…”.

## Extractors

`find_extractor(parsed)` walks registered platform extractors. If none match,
the analyzer performs a streaming GET, sniffs the first 8 KiB, and classifies
the resource as a direct file or an HTML page.

Platform extractors use yt-dlp with cookies, credentials, and geo-bypass
disabled. Failures map to typed errors instead of being circumvented.

## Tools

Tools register a `ToolSpec` (id, inputs, accepted resource types, options
model, runtime requirements). The frontend renders only tool ids returned by
analyze or upload.

Optional requirements:

- `ffmpeg`: video/audio tools
- `platform_extractors`: yt-dlp
- `browser`: screenshot and URL→PDF (`AD_ENABLE_BROWSER_TOOLS`)

## Frontend

The web app is a Next.js 16 App Router project. It talks to the API through
same-origin `/api/v1` rewrites. User-facing strings live in `src/lib/copy.ts`
and `src/lib/catalogue.ts`. Dark/light mode uses `next-themes`.

## Why no extra packages

Shared TypeScript types live in `apps/web/src/lib/api.ts` and mirror the
OpenAPI models. A `packages/` workspace exists in `pnpm-workspace.yaml` for
future extraction; it is empty on purpose.

## Verification

| Item | Status |
| --- | --- |
| Modular analyze → capability → job → worker path | Implemented |
| Frontend renders API tool ids / hides unavailable runtimes | Implemented |
| Long-running work in workers | Implemented |
| Streamed uploads/downloads with TTL storage | Implemented |
| Load-tested multi-replica / shared storage | **NOT VERIFIED** / known limitation |
