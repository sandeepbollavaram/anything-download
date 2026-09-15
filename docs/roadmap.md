# Roadmap

Ordered by dependency. Production gates come first; nothing below them should ship
to users before they are met. Items are documented here, not implemented, unless
marked done.

## 0. Production gates (in progress)

- [x] Global resource limits: storage guard, request-body cap, FFmpeg thread cap,
      output-size enforcement, Redis AOF
- [x] Production Compose overlay: HTTPS edge, no application ports, container limits
- [x] CI covering API, web, E2E on the production build, Docker smoke, extension, audits
- [x] CI executed on a pushed revision (all jobs green on `main`)
- [ ] Staging environment deployed and verified (public TLS, firewall, real jobs)
- [ ] Production monitoring (see [observability](engineering/observability.md))

## Launch plan for anythingdownload.in

The domain is registered with GoDaddy; DNS is not connected yet. Steps, in order
(details in [deployment.md](deployment.md)):

1. **Staging server.** Rent a small VPS (2 vCPU, 4 GB RAM, Ubuntu 24.04), harden
   SSH, install Docker, apply the firewall.
2. **Staging DNS.** In GoDaddy add `A staging -> STAGING_SERVER_IPV4`; wait until it
   resolves publicly.
3. **Deploy staging** with `AD_DOMAIN=staging.anythingdownload.in` and a `noindex`
   header; confirm Caddy obtains the certificate.
4. **Verify staging:** health and readiness, SSRF refusal, real jobs, the browser test
   suite, the Chrome extension pointed at staging, and a day of normal use.
5. **Monitoring minimum:** an external uptime check on `/api/v1/ready` and
   certificate expiry alerts, before any public traffic.
6. **Production server and DNS:** remove GoDaddy's parked `A @` record, add
   `A @ -> SERVER_IPV4` (and `CNAME www -> anythingdownload.in` with a Caddy
   redirect if `www` is wanted).
7. **Deploy production** from the exact commit verified on staging; repeat the
   smoke tests; keep the previous commit ready for rollback.
8. **After launch:** Chrome Web Store submission, request and error-rate metrics,
   per-client active-job caps, and the FFmpeg upgrade.

## 1. Chrome extension: first version built

Popup, context menu, honest capability states, minimal permissions, automated tests
([docs/extension.md](extension.md)). Remaining: Chrome Web Store listing and review,
manual `activeTab` check on a real install.

## 2. PWA / mobile install

The web app already has a manifest and service worker. Next: an install prompt that
respects user choice, an offline page that says what works offline (nothing that
needs the server), and share-target support so a mobile "Share" can send a URL to
the analyzer.

## 3. Bookmarklet

A one-line bookmarklet that opens `/analyze?url=<current page>`. No script injection
into the page beyond reading `location.href`; useful where extensions are unavailable.

## 4. Developer API and 5. API documentation

The public API is already versioned (`/api/v1`) and described by OpenAPI. Before
inviting developers: API keys with per-key quotas (keyed limits in the existing Redis
limiter), a published, stable subset of endpoints, a hosted reference generated from
the OpenAPI schema (docs stay off in production until then), and a deprecation policy.

## 6. URL intelligence / capability engine

Grow `analyze` into a clearer capability model: per-URL capability explanations
("why not"), confidence for detected media, and consistent reason codes across
extractors, so every client (website, extension, API users) shows the same honest
answer.

## 7. Universal analyzer homepage

Make "paste anything" the single entry point: URL, file or text, with the tool list
driven entirely by the capability engine rather than per-page presets.

## 8. Observability

See [engineering/observability.md](engineering/observability.md): request and error
rates, failed jobs by code, active jobs and workers, Prometheus exposition, host
metrics, external probes and alerts.

## 9. Abuse prevention

Per-client active-job caps (today only the global queue fails closed), adaptive rate
limits under load, and a CDN or WAF in front of the edge, configured with correct
`trusted_proxies` so client identity is preserved.

## 10. Automated extractor health checks

A scheduled job (outside default CI) that exercises each platform extractor against
known public test content and reports breakage, so yt-dlp or platform changes are
noticed before users do.

## 11. Staging environment and 12. production monitoring

A staging host deployed with the production overlay from CI on every merge, with the
post-deploy checks from [deployment.md](deployment.md) automated; production deployed
only from a verified staging revision.

## 13. Automated security regression suite

Promote today's manual red-team checks into scheduled tests against staging: the live
SSRF matrix, forged `X-Forwarded-For`, oversized bodies and uploads, result-serving
headers, and dependency and image CVE scans.

## 14. Optional browser-tool worker

A separate worker image with Chromium for screenshots and URL-to-PDF, isolated from
the main worker, with the navigation host pinned (already implemented) and resource
limits of its own. Enabled per deployment; the API already reports the tools as
unavailable when Chromium is absent.

## 15. Other browser extensions

Firefox or Safari ports only if there is demand; the extension has no Chrome-specific
logic beyond `chrome.*` APIs, most of which have WebExtension equivalents.

## Boundaries that do not change

Public resources the user is authorized to use only. No bypass of DRM, logins,
paywalls, CAPTCHAs, region restrictions or other access controls. No private account
extraction, no credential or cookie collection. Privacy-first, no unnecessary tracking.
