# Security

This document describes the controls that are implemented, not a wishlist.

## Trust boundary

Every URL, filename, `Content-Disposition` value, and uploaded byte stream is
untrusted.

## SSRF

`security.urls` rejects:

- schemes other than `http` and `https` (`file`, `ftp`, `javascript`, `data`, …)
- URLs with userinfo
- loopback, private, link-local, multicast, reserved IPv4/IPv6
- IPv4-mapped, 6to4, Teredo, and NAT64 embeddings of blocked IPv4
- cloud metadata hostnames and well-known metadata IPs
- single-label and `.local` / `.internal` / `.localhost` names
- unusual IPv4 spellings (decimal, hex, octal, shortened forms such as
  `2130706433`, `127.1`, `0x7f.0.0.1`), parsed portably without `inet_aton`

Resolved IP literals are canonicalized before the connect pin so a public
decimal form such as `134744072` (`8.8.8.8`) is not false-blocked, and a
private form cannot slip through as a raw host string.

`validate_and_resolve` resolves DNS and requires **every** answer to pass the
IP policy.

`SafeHttpClient` then connects to the **validated IP**, sending the original
host via `Host` and TLS SNI. Redirects are followed manually and re-validated.
Connection reuse is disabled.

`AD_ALLOW_PRIVATE_TARGETS` exists for tests only and is refused when
`AD_ENV=production`. OpenAPI docs are off in production unless the process
environment sets `AD_ENABLE_DOCS` to a truthy value.

## Downloads and uploads

- Bodies are streamed to disk, never fully buffered
- `AD_MAX_FILE_SIZE_MB` and `AD_MAX_UPLOAD_SIZE_MB` are enforced while writing
- MIME type prefers magic bytes over headers and extensions
- SVG is accepted as an image for download, but processing tools reject it
- Empty uploads are rejected

## Filenames

`sanitize_filename` strips path components, control characters, reserved
Windows device names, and bounds length. `Content-Disposition` is never
trusted as a path.

Storage identifiers must match `^[a-f0-9]{32}$`. `LocalStorage.resolve_within`
rejects path escape, and refuses any name containing a backslash or NUL byte on
every platform: on Linux such a name stays inside the directory, but would
traverse if the stored tree were ever read on Windows.

## Process isolation

FFmpeg/FFprobe:

- argument arrays only
- `-protocol_whitelist file,crypto,data,pipe` so a crafted playlist cannot
  open `http`/`https`/`tcp` (SSRF past the HTTP client)
- `safe_path` refuses option-like and protocol-like names
- hard timeout, kill on cancel
- no shell
- output is capped at `AD_MAX_FILE_SIZE_MB` twice: ffmpeg's own `-fs` stops the
  muxer once the file passes the limit (overshoot of roughly one packet), and
  the file is also polled once a second and the process killed if it grows past
  the limit anyway (`-fs` is ignored by some outputs). Verified with real ffmpeg:
  before `-fs`, a raw 1080p stream reached 142 MB against a 3 MB cap

Playwright (optional) is given a validated URL and a filesystem destination,
not a user-built command line. Every subrequest is re-resolved (allows are
not cached) and unusual IPv4 literals are interpreted the same way as the
HTTP client. Output files over `AD_MAX_FILE_SIZE_MB` are deleted.

The navigation host is additionally pinned inside Chromium via
`--host-resolver-rules=MAP <host> <validated ip>`. The route policy can only
re-resolve a name and then hand the request back to Chromium, which resolves it
again itself; the resolver rule removes that gap for the target host. Unlike
rewriting the URL to an IP it leaves the hostname intact, so SNI and
certificate validation are unaffected. **Known limitation:** sub-resources on
*other* hosts are still covered only by the per-request policy, so a narrow
rebinding race remains for third-party sub-resources.

yt-dlp follows its own sockets after the initial URL is validated, and is not
IP-pinned. What bounds this is that yt-dlp is only ever invoked for a host on a
registered extractor's fixed allowlist (`extractors/platforms/*`); there is no
generic or wildcard fallback, so it is not reachable for an arbitrary
user-supplied host. Exploiting the missing pin would require controlling DNS for
a major platform's own domain. `tests/security/test_extractor_domains.py` pins
the matcher down so a loosened rule (substring instead of suffix) fails loudly.
Signed query strings in its log text are redacted. It does not receive cookies
or geo-bypass options.

## Documents and images

- PDF page limit (`AD_MAX_PDF_PAGES`)
- encrypted / password PDFs rejected
- Pillow `MAX_IMAGE_PIXELS` and `AD_MAX_IMAGE_PIXELS`
- ZIP creation is output-only; user archives are not extracted
- webpage fetch is size- and resource-capped; JavaScript is not executed
  except in the optional sandboxed browser tools

## Privacy

- No accounts for core tools
- No advertising or third-party analytics scripts
- Result TTL defaults to 30 minutes
- Logs redact credentials, cookies, and query strings
- Job views do not include the source URL

## Abuse controls

- Redis fixed-window rate limits per IP (analyze / jobs / uploads / general)
- Queue depth limit
- Concurrent jobs per worker
- Job duration limit
- 429 responses include `Retry-After`

Enable `AD_TRUST_PROXY_HEADERS` only behind a trusted proxy. The client address
is then the **rightmost** `X-Forwarded-For` entry, the one the proxy appended;
entries to its left are client-supplied. Using the leftmost entry let a client
rotate a forged header and never be rate limited (reproduced against nginx with
`$proxy_add_x_forwarded_for`: 45/45 requests accepted against a 30/minute limit).
Behind more than one proxy hop the rightmost entry is the inner proxy, which errs
toward over-throttling rather than bypass.

## Resource limits

The threat is many clients at once: large URLs, large uploads, expensive jobs,
many FFmpeg processes, temporary files. Each limit below fails closed with a
typed error; none depends on the client behaving.

| Resource | Limit | On breach |
| --- | --- | --- |
| JSON/form request body | `AD_MAX_REQUEST_BODY_KB` (256 KB), declared or chunked | 413 before parsing |
| URL length | `AD_MAX_URL_LENGTH` (2048) | 414 |
| Upload | `AD_MAX_UPLOAD_SIZE_MB` (200), from `Content-Length` and while streaming | 413, partial file deleted |
| Remote file / result | `AD_MAX_FILE_SIZE_MB` (500); ffmpeg `-fs` + kill watchdog; runner backstop | `FILE_TOO_LARGE`, file deleted |
| Job duration | `AD_MAX_JOB_DURATION_SECONDS` (600) | `PROCESSING_TIMEOUT`, ffmpeg killed |
| Concurrency | `AD_MAX_CONCURRENT_JOBS` per worker (2) | jobs wait in the queue |
| CPU per job | `AD_FFMPEG_THREADS` (2) for decoders, encoder and filters | None |
| Queue | `AD_MAX_QUEUE_DEPTH` (200) | 503 `QUEUE_FULL` + `Retry-After` |
| Disk (global) | `AD_MIN_FREE_DISK_MB` floor (2048; 4096 in production), optional `AD_MAX_STORAGE_MB` quota | 503 `STORAGE_FULL` + `Retry-After` for new uploads and jobs; an upload stream is aborted if it crosses the floor; an admitted job that has not started fails retryably |
| Retention | results and uploads 30 min, job records 2 h, orphans swept | files deleted |
| Request rate | per-IP buckets (analyze / jobs / uploads / general) in Redis | 429 + `Retry-After` |
| Containers (production) | CPU, memory, PIDs, log rotation per service | the kernel enforces |

The storage guard reads free space with one `statvfs` per check; the optional
quota walks the storage tree at most every 15 s. An unreadable filesystem counts
as full. `/api/v1/ready` reports `storage_space` without failing readiness, so
status checks and downloads keep working under disk pressure, and
`/api/v1/metrics` exposes `storage_free_bytes` and `storage_pressure`. Verified
for real in a container whose storage was a 64 MB tmpfs with a 40 MB floor: an
8 MB upload was accepted, a 30 MB upload was refused with 503 `STORAGE_FULL`,
and further uploads were refused once real usage crossed the floor.

**Known limitation:** there is no per-client cap on active jobs. One client within
its rate limit can occupy a large share of the queue; the queue then fails closed
(`QUEUE_FULL`) for everyone rather than degrading per client.

## Result size

Beyond the per-tool limits, `JobRunner._publish` refuses to publish any result
file larger than `AD_MAX_FILE_SIZE_MB` and deletes it. This backstops tools that
never run through ffmpeg (PDF, image, browser).

## Serving results

Results are downloaded from `/api`, which production routes on the site's own
origin, so a result file is treated as hostile content from that origin:

- only raster images, audio, video, PDF and plain text are served `inline`;
  everything else (SVG in particular) is served as an `attachment`
- every result except PDF carries `Content-Security-Policy: default-src 'none';
  … sandbox`, so a file opened directly cannot run script. PDF is exempt because
  Chrome refuses to render a sandboxed PDF, which would break the preview iframe
- `X-Content-Type-Options: nosniff`

Before this, an SVG with an embedded `<script>` fetched by `image-downloader` was
served `inline` as `image/svg+xml` with no CSP. `file-downloader` refuses HTML
("returned a webpage instead of a file"), so HTML cannot become a result.

Job creation also rejects an upload whose type the tool cannot process
(`FILE_TYPE_UNSUPPORTED`, 415) instead of queueing a job certain to fail.

## Browser-facing headers

The API sets `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`
and `Cache-Control: no-store`. The Next.js app additionally sends, for every
route:

| Header | Value |
| --- | --- |
| `Content-Security-Policy` | see below |
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=()` |
| `Strict-Transport-Security` | `max-age=63072000; includeSubDomains` |

The CSP is `default-src 'self'` with `frame-ancestors 'none'`, `object-src
'none'`, `base-uri 'self'` and `form-action 'self'`.

**Known limitation:** `script-src` includes `'unsafe-inline'`. Next.js injects
inline bootstrap scripts on every page; without it React does not hydrate and
the site renders but does not respond to input. The alternative, a per-request
nonce from middleware, would force all 54 static routes to render dynamically.
What the policy still guarantees is that no third-party script origin can load,
and this app ships no ads, analytics or CDN scripts. `img-src` allows `https:`
because thumbnails are hotlinked from arbitrary platform CDNs.

## Production responses

Unhandled exceptions return `INTERNAL_ERROR` without a stack trace when
`AD_ENV=production`.
