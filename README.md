# Anything Download

Free tools for the open web.

**No ads. No account. No nonsense.**

Anything Download is a privacy-first, open-source web utility that analyzes
publicly accessible URLs and files, then performs legitimate download,
conversion, compression, extraction, and metadata operations.

It does **not** claim to download anything from anywhere. It downloads and
processes publicly accessible files and media you have permission to use.

Planned production domain: [anythingdownload.in](https://anythingdownload.in)
(configure via environment variables; the domain is not hard-coded).

## What it does

Paste a URL or upload a file. The service:

1. Normalizes and validates the URL
2. Blocks private, local, and reserved network targets
3. Detects the resource type (file, webpage, or supported public platform)
4. Returns only the tools that actually apply
5. Runs the work as a background job
6. Serves a temporary result
7. Deletes the file automatically

If a source is unsupported, private, DRM-protected, or otherwise restricted,
you get a clear explanation, not a broken download button.

## Features

- Single intelligent input on the homepage
- Direct file analysis (magic bytes, not just extensions)
- Image, PDF, audio, and video tools
- Generic webpage resource finder
- Plugin-style platform extractors for public content only
- Redis-backed job queue with real progress when measurable
- Automatic TTL cleanup
- No login for core tools
- No advertising or third-party tracking scripts

## Architecture

```
apps/web     Next.js 16 frontend
apps/api     FastAPI backend, extractors, tools, workers
docker/      Production images
docs/        Architecture, security, API, jobs, deployment
```

The API, worker, and cleanup process share one Python package. Redis stores
job state. Files live in a local directory (S3-compatible storage can replace
it later). PostgreSQL is not required.

See `docs/architecture.md`.

## Local development

Prerequisites: Python 3.12, Node 22, pnpm 10, Redis, FFmpeg/FFprobe.

```bash
cp .env.example .env
# start Redis (or: docker compose up redis)

cd apps/api
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -e ".[dev]"
uvicorn anything_download.main:app --reload --port 8000

# other terminals
python -m anything_download.workers.worker
python -m anything_download.workers.cleanup

# web
pnpm install
pnpm --filter @anything-download/web dev
```

Open http://localhost:3000. API docs: http://localhost:8000/api/v1/docs

Full walkthrough: `docs/local-development.md`.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

Services: `web`, `api`, `worker`, `cleanup`, `redis`.

## Environment variables

Every environment-specific value is documented in `.env.example`. Backend
variables use the `AD_` prefix. Frontend variables use `NEXT_PUBLIC_`.

Do not commit secrets. There are no required third-party API keys for core
features.

## Testing

```bash
# API (fakeredis; no live third-party sites)
cd apps/api && pytest -q -m "not external and not browser"

# Web
pnpm --filter @anything-download/web lint
pnpm --filter @anything-download/web typecheck
pnpm --filter @anything-download/web build
pnpm --filter @anything-download/web test:e2e
```

Default CI is deterministic. Platform extractors are tested with fixtures, not
random public websites. GitHub Actions starts Redis, the API, and a worker for
Playwright API flows (`E2E_API=1`).

## Verification status

| Check | Status |
| --- | --- |
| API lint / format / mypy / pytest (no external/browser) | Implemented; run locally before each release |
| Web lint / typecheck / production build | Implemented; run locally before each release |
| Playwright UI (no API) | Implemented in `apps/web/e2e` |
| Playwright + local API | Implemented; requires Redis + API + worker or the CI e2e job |
| Docker image build / compose stack | Files exist; **not verified in every environment** |
| Live platform extractors | Mocked in CI; live behavior is a **known limitation** |

Do not call a revision production-ready until that revision’s quality gate
has actually been run. See `docs/engineering/testing-strategy.md`.

## Deployment

See `docs/deployment.md`. Do not treat a checkout as production-ready until
lint, typecheck, tests, and image builds have passed on that revision.

## Security

Treat every URL as untrusted. SSRF protection, filename sanitization, process
timeouts, and size limits are documented in `docs/security.md` and `SECURITY.md`.

To report a vulnerability, follow `SECURITY.md`. Do not open a public issue.

## Contributing

See `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.

## License

MIT. See `LICENSE`.
