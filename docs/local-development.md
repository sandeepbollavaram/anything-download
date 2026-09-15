# Local development

## Prerequisites

- Python 3.12
- Node.js 22 and pnpm 10
- Redis 7
- FFmpeg and FFprobe on `PATH` (or set `AD_FFMPEG_BIN` / `AD_FFPROBE_BIN`)
- Optional: Playwright Chromium if you enable browser tools

## Environment

```bash
cp .env.example .env
```

For local work the defaults are enough. Point `AD_FFMPEG_BIN` at a full path
if the binaries are not on `PATH`.

## Redis

```bash
docker compose up redis
# or a local redis-server
```

## API

```bash
cd apps/api
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate
pip install -e ".[dev]"
# optional browser extras:
# pip install -e ".[dev,browser]"

uvicorn anything_download.main:app --reload --host 127.0.0.1 --port 8000
```

Worker and cleanup (separate terminals, same venv):

```bash
python -m anything_download.workers.worker
python -m anything_download.workers.cleanup
```

Health: http://localhost:8000/api/v1/health
Docs: http://localhost:8000/api/v1/docs

## Web

```bash
pnpm install
pnpm --filter @anything-download/web dev
```

http://localhost:3000 proxies `/api/*` to `NEXT_PUBLIC_API_URL`
(default `http://localhost:8000`).

## Tests

```bash
cd apps/api
pytest -q -m "not external and not browser"

pnpm --filter @anything-download/web lint
pnpm --filter @anything-download/web typecheck
pnpm --filter @anything-download/web build
```

Playwright e2e starts the Next.js dev server. Tests that need a live API skip
unless `E2E_API=1`.

## Browser tools

```bash
# in apps/api
pip install -e ".[browser]"
playwright install chromium
```

Set `AD_ENABLE_BROWSER_TOOLS=true`. Screenshot and URL→PDF remain unavailable
until that flag and Chromium are present.

## Verification notes

Default `pnpm --filter @anything-download/web test:e2e` is UI-only (no API).
For API-backed Playwright:

```bash
# Redis, API, and worker must already be running
set E2E_API=1
pnpm --filter @anything-download/web test:e2e
```

Do not point default e2e at live third-party platforms.
