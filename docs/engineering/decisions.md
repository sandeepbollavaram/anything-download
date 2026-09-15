# Engineering decisions

These are decisions that are implemented, not a backlog.

| Decision | Choice | Why |
| --- | --- | --- |
| Persistence | Redis + local disk, no PostgreSQL | Jobs and uploads are ephemeral. A database would outlive the product promise. |
| Queue | Redis list + worker heartbeat | Simple, testable with fakeredis, enough for a single-region free service. |
| HTTP egress | IP-pinned client | Reduces DNS rebinding between check and connect. |
| Platform media | yt-dlp, no cookies, no geo-bypass | Public listings only. Failures become typed errors. |
| Browser tools | Off by default | Playwright/Chromium is optional and high-risk if always on. |
| Progress | Real signals only | Invented percentages would be fake functionality. |
| Frontend tools | API-driven, hide unavailable runtimes | SEO pages may exist; Start is not offered when the worker cannot run the tool. |
| CI E2E | Redis + API + worker in GitHub Actions | Default path does not need a hosted API or live platforms. |
| Storage portability | Local adapter only | S3 is specified as a future swap, not built in this phase. |
