# Release candidate status

Snapshot of what has actually been verified for this revision, and what has not.
Update it whenever a gate changes; never mark a gate verified without evidence.

| Item | Status |
| --- | --- |
| Project | Anything Download |
| Date of verification | 2026-09-15 |
| Release status | **READY FOR CI** (local release candidate, fully validated locally) |
| UI | 8.6/10 release baseline (redesign frozen) |
| CI | **NOT VERIFIED** (the workflow has never run; it needs a push) |
| Staging | **NOT DEPLOYED** (no server yet) |
| Production | **NOT DEPLOYED** (no server yet) |
| Domain | `anythingdownload.in`, purchased through GoDaddy; DNS not connected to any server |
| Docker | Verified locally; Docker Desktop data lives on drive D: (unchanged) |

## Local test results (run on 2026-09-15)

| Suite | Result |
| --- | --- |
| API lint and types | ruff check, ruff format check, mypy (65 files): all clean |
| API tests (host, no FFmpeg) | 326 passed, 2 skipped (both need FFmpeg) |
| API FFmpeg tests (inside the API image) | the two skipped modules: 21 passed, 0 skipped |
| API security subset | 182 passed, 1 skipped (FFmpeg), covering SSRF, redirects, DNS rebinding, client IP, result serving, hardening, output and resource limits |
| Web | lint, typecheck and production build pass |
| Browser (Playwright, against the Docker stack) | 46/46 passed. One earlier run right after the containers started had 1 transient failure; the next two full runs passed |
| Extension | typecheck; unit 22/22; browser 20 passed, 2 skipped by default; the 2 live API tests passed against the Docker API (`EXT_REAL_API_ORIGIN=http://127.0.0.1:8000`) |
| Clean export (only committable files, fresh virtualenv, frozen pnpm install) | API tests 326 passed / 2 skipped, web lint, typecheck and build, extension checks, and both Docker images: all pass |

## Infrastructure and security results

Production overlay started from the clean export, with no `.env`,
`AD_DOMAIN=localhost`, host ports 8080/8444:

- Only Caddy publishes ports; Redis, API, web, worker and cleanup publish none.
- CPU, memory and PID limits, `no-new-privileges`, dropped capabilities, restart
  policies and log rotation on every service; application images run as uid 10001.
- HTTPS through Caddy; web security headers present (CSP, HSTS, X-Frame-Options,
  nosniff, Referrer-Policy, Permissions-Policy); API docs return 404.
- `/api/v1/metrics` returns 404 at the edge and 200 inside the Docker network.
- SSRF: loopback, `localhost`, private range, cloud metadata, IPv6 loopback,
  internal hostname, hex and decimal IP encodings refused; credentials in URLs
  and `file://` rejected.
- Real jobs through the edge: FFmpeg video to MP3 and a QR code completed; results
  downloaded with safe `Content-Disposition`; delete removes the result.
- Uploads: traversal filename sanitised, MIME detected from content, 256 KB JSON
  body limit (413).
- Rate limiting: 40 requests with forged `X-Forwarded-For` values were limited
  after 30.

## Fixed in this pass

- `docker-compose.yml` required a `.env` file, so a fresh clone and the CI Docker
  job would fail before starting. `.env` is now optional.
- `docker/api-entrypoint.sh` and both Dockerfiles had CRLF line endings in the
  working tree; a local build produced API containers that could not start.
  Normalised to LF (as `.gitattributes` requires) and the API image now strips
  carriage returns from the entrypoint defensively.
- `deploy/Caddyfile`: `/api/v1/metrics` is no longer served publicly.
- `apps/web/AGENTS.md` (written by `next dev` for AI coding agents) is ignored
  like `CLAUDE.md`.
- Deployment guide: DNS records, HTTPS, firewall, staging and production runbook,
  rollback, logs and recovery.

## Known limitations

- CI requires a push before it can be verified.
- A real staging deployment requires a server.
- Browser tools (screenshot, URL to PDF) are off by default and need validation
  with real Chromium in a custom worker image.
- The extension popup layout remains basic (brand colours and logo only).
- No formal axe accessibility audit has been performed.
- No cross-browser review (Safari, Firefox) has been performed.
- No per-client active-job cap: one client within its rate limit can fill a large
  share of the queue, which then fails closed for everyone.
- Live platform availability varies (for example YouTube may rate limit or ask a
  server to prove it is not a bot); such sources are refused, never bypassed.
- Request rate, error rate and failure-code metrics are not implemented yet, and
  nothing scrapes or alerts on the existing counters (see
  [observability](engineering/observability.md)).
- FFmpeg in the image is Debian 12's 5.1 with unfixed upstream CVEs (see the
  [threat model](engineering/threat-model.md)).

## Human gates (not crossed)

These require the owner's authorisation and were not performed: `git add`,
`git commit`, `git push`, GoDaddy DNS or nameserver changes, creating servers or
cloud accounts, spending money, using credentials, and any staging or production
deployment.

## Next human actions

1. Review the working tree, then commit and push when satisfied, and watch CI.
2. Create a staging server, add the `staging` A record, and follow
   [deployment](deployment.md#staging-and-production-runbook).
3. Run the staging smoke tests and a manual check of the Chrome extension.
4. Decide on the FFmpeg upgrade and the per-client active-job cap.
5. Create the production server and `@` (and optional `www`) records, deploy,
   and repeat the smoke tests.
