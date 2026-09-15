# Threat model

This document matches the current implementation. It is not a claim that the
service has been penetration-tested in production.

| Asset | Threat | Surface | Likelihood | Impact | Mitigation | Remaining risk |
| --- | --- | --- | --- | --- | --- | --- |
| Internal networks | SSRF | Analyze, jobs, webpage fetch, browser tools | High | High | Scheme/host/IP policy, unusual IPv4 parsing, DNS validation, IP-pinned HTTP, redirect re-validation, production refuses `AD_ALLOW_PRIVATE_TARGETS` | Resolver/OS differences; new IP encodings |
| DNS | Rebinding | Outbound HTTP | Medium | High | Validate every A/AAAA, connect to pinned IP + Host/SNI | Rare split-horizon after pin if process reused incorrectly (keepalive is off) |
| Uploads | Malware / bombs | `POST /uploads` | High | Medium | Stream to disk, size cap, magic-byte sniff, reject HTML-as-image, pixel/page limits | Novel formats |
| Media | FFmpeg/parser bombs and memory-safety bugs | Video/audio tools | Medium | High | Arg arrays, protocol whitelist (file/pipe only), timeouts, duration cap, output capped by ffmpeg `-fs` plus a kill watchdog, no shell; container runs non-root with all capabilities dropped, `no-new-privileges`, memory/PID limits | **Debian 12's FFmpeg 5.1.9 has ~16 HIGH CVEs with no Debian fix yet** (Trivy, 2026-09-14). Upgrading FFmpeg (newer base OS or a maintained static build) is the top open security item |
| PDFs | Page/image bombs | PDF tools | Medium | Medium | Page limit, encrypted reject, pixel cap on render | Complex PDF features skipped, not fully sandboxed |
| Images | Decompression / pixel bombs | Pillow | Medium | Medium | `MAX_IMAGE_PIXELS`, SVG rejected for processing | Pillow CVEs |
| Archives | Zip bombs | Split output only | Low | Medium | User archives are not extracted | If extraction is added later, must bound it |
| Filenames | Traversal / device names | Downloads, uploads | Medium | Medium | Sanitize + hex storage IDs + `resolve_within` | Locale-specific Unicode tricks |
| Queue | Flooding | `POST /jobs` | High | Medium | Rate limits, queue depth, concurrency, job TTL | Distributed attackers behind one NAT; no per-client active-job cap |
| Disk | Exhaustion by many uploads/jobs | Uploads, results, temp files | Medium | High | Global free-space floor and optional quota (503 `STORAGE_FULL`), per-file caps, TTL cleanup, Docker log rotation | Floor must be sized for concurrent in-flight jobs |
| Memory | Oversized JSON bodies | `POST /analyze`, `/jobs` | Medium | Medium | 256 KB body limit (declared and chunked), container memory limits | None |
| Extension | Data leakage / over-permission | Chrome extension | Low | Medium | `activeTab` + `contextMenus` + `storage` only; one host permission; no content scripts or remote code; URL sent only on user action; manifest guard test | A user can point it at a self-hosted server they choose |
| Redis | Data leak / DoS / data loss | Network | Low if firewalled | High | No auth, so compose publishes it on `127.0.0.1` only; no user URLs in job views | Misconfigured production Redis; AOF `everysec` can lose ~1 s of writes on a crash |
| Storage | Residual files | Disk | Medium | Medium | TTL cleanup, orphan sweep, fail/cancel delete | Shared volume required for multi-replica |
| Browser tools | SSRF via page subrequests | Screenshot, URL→PDF | Medium | High | Off by default; navigation host pinned in Chromium via `--host-resolver-rules`; re-resolve every sub-request host (no allow cache); unusual IPv4; output size cap | Sub-resources on other hosts are policy-checked but not pinned, so a narrow rebinding race remains; JS can consume CPU until timeout |
| Platforms | SSRF via yt-dlp sockets | yt-dlp extractors | Low | High | yt-dlp only runs for hosts on a fixed per-extractor allowlist (no generic fallback); initial URL validated; matcher covered by regression tests | No IP pin inside yt-dlp: would matter only if DNS for a listed platform domain were attacker-controlled |
| Platforms | Abuse / ToS | yt-dlp extractors | Medium | Legal/ops | No cookies, no geo-bypass, typed restriction errors, CI mocked | yt-dlp breakage; operators must watch ToS |
| Results | Stored XSS via downloaded SVG | `GET /jobs/{id}/result` on the site origin | Medium | High | Inline only for raster/audio/video/PDF/text; SVG and others as attachment; sandbox CSP on every non-PDF result; nosniff | PDF served inline without sandbox (Chrome viewer isolates PDF JS) |
| Rate limits | Bypass via forged `X-Forwarded-For` | Any endpoint behind a proxy | High if trusted | Medium | Rightmost XFF hop only when `AD_TRUST_PROXY_HEADERS=true` | Multi-hop proxies over-throttle (inner proxy address) |
| Frontend | XSS / clickjacking | Next.js app | Medium | High | CSP (`default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`), `X-Frame-Options: DENY`, HSTS, Permissions-Policy; React escaping; no third-party scripts | `script-src` needs `'unsafe-inline'` for Next's bootstrap, so CSP does not stop injected inline script; it only stops third-party origins |
| Logs | Secret leak | stderr | Medium | High | Redact cookies, tokens, query strings | Mis-added log fields |
| Docs | Info leak | `/api/v1/docs` | Low | Low | Disable with `AD_ENABLE_DOCS=false` | Default is on in development |
| Dependencies | Supply chain | pip/pnpm/images | Medium | High | Lockfiles; pip-audit and `pnpm audit --prod` in CI; Trivy image scan in CI fails on fixable HIGH/CRITICAL; images apply Debian security updates; web runtime ships without npm/corepack | Base-OS findings without an upstream fix (API image 246, web 56 HIGH/CRITICAL on 2026-09-14) remain until Debian ships fixes |

Recommended next mitigations (not implemented):

- Shared object storage for multi-replica
- Out-of-process seccomp/gVisor for FFmpeg if threat model requires it
- Upgrade FFmpeg beyond Debian 12's 5.1.9 (newer base OS or a maintained static build), then re-run the real media pipeline tests
- Production WAF / proxy IP allowlist in front of Redis
