# Testing strategy

## Layers

| Layer | Where | Default CI |
| --- | --- | --- |
| Unit | `apps/api/tests/unit` | Yes |
| Security | `apps/api/tests/security` | Yes |
| Integration | `apps/api/tests/integration` (fakeredis, respx) | Yes |
| Frontend lint/type/build | `apps/web` | Yes |
| Playwright UI | `apps/web/e2e` without `E2E_API` | Yes (homepage, legal, theme, tool pages) |
| Playwright + API | same folder, skipped unless `E2E_API=1` | Yes on the e2e job (starts Redis/API/worker) |
| `@pytest.mark.external` | live platforms | No |
| `@pytest.mark.browser` | Playwright Chromium in API | No |
| Docker image build | `docker/*.Dockerfile` | Yes in the docker job |

## Rules

- No live YouTube/Instagram/TikTok in default CI.
- Do not delete or weaken tests to go green.
- Do not claim a check passed unless it ran.

## Rate limiting and test isolation

Rate limits are keyed by client IP + route bucket, and every E2E test shares one
source IP. `e2e/rate-limit.spec.ts` deliberately exhausts the `/analyze` bucket,
so running it alongside the other analyze-backed specs starves them and they
fail with 429 instead of their real assertion. `test:e2e` therefore runs the
suite in two passes: everything except `rate limit`, then that spec alone with
`--workers=1`. Keep new analyze-flooding tests in that second pass.

**Known limitation:** the flood still poisons the bucket for up to a minute
*after* it finishes, so re-running analyze-backed specs immediately afterwards
(common when iterating locally) fails with 429. Wait out the window, or point
the run at a fresh API. CI is unaffected because the job ends after the second
pass.

## Locators

Two ambiguities bite `getByRole` in this app:

- Next.js injects an always-empty `role="alert"` route announcer, so
  `getByRole("alert")` matches it too. Exclude `#__next-route-announcer__`.
- The header wordmark is a link named "Anything Download", so
  `getByRole("link", { name: "Download" })` matches it. Use `exact: true`.

Rejection messages are rendered twice on purpose (a visible panel plus an
`sr-only` live region); assert against the visible one.

## Local commands

```bash
cd apps/api && pytest -q -m "not external and not browser"
pnpm --filter @anything-download/web lint
pnpm --filter @anything-download/web typecheck
pnpm --filter @anything-download/web build
# UI-only e2e:
pnpm --filter @anything-download/web test:e2e
# Full API e2e (Redis + API + worker must already be up):
set E2E_API=1
```
