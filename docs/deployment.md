# Deployment

Production domain: `https://anythingdownload.in` (registered with GoDaddy).
Staging domain: `https://staging.anythingdownload.in`. Both are set through
environment variables; nothing is hard-coded.

With the bundled production overlay (recommended) the only value you must set is
`AD_DOMAIN`; `docker-compose.prod.yml` derives the rest:

```
AD_DOMAIN=anythingdownload.in          # staging: staging.anythingdownload.in
# Derived by docker-compose.prod.yml (shown for reference, do not duplicate):
#   AD_ENV=production  AD_LOG_FORMAT=json  AD_ENABLE_DOCS=false
#   AD_TRUST_PROXY_HEADERS=true  AD_RATE_LIMIT_ENABLED=true
#   AD_ALLOW_PRIVATE_TARGETS=false  AD_PUBLIC_URL=https://$AD_DOMAIN
#   NEXT_PUBLIC_SITE_URL=https://$AD_DOMAIN  NEXT_PUBLIC_API_URL=http://api:8000
```

`NEXT_PUBLIC_API_URL` is the address the **Next.js server** uses to reach the
API, so behind Compose it is `http://api:8000`, not the public origin (see the
note below). Browsers always call same-origin `/api`, and the reverse proxy
routes:

- `/api/*` to the API
- everything else to the web app

A `.env` file is optional for Compose; copy `.env.example` only if you need to
override a limit.

## Process model

| Process | Command |
| --- | --- |
| API | `uvicorn anything_download.main:app --host 0.0.0.0 --port 8000` |
| Worker | `python -m anything_download.workers.worker` |
| Cleanup | `python -m anything_download.workers.cleanup` |
| Web | `node apps/web/server.js` (standalone output) |
| Redis | Redis 7+ with AOF (see persistence note below) |

**Redis persistence.** Run Redis with AOF (`--appendonly yes --appendfsync
everysec`) on a persistent volume, as the bundled compose file does. Redis holds
the queue, per-worker processing lists, job records and upload metadata, while
the files live on the storage volume. Without persistence a Redis restart drops
every queued and in-flight job (users see `JOB_NOT_FOUND`) and strands their
files for the orphan sweep. With AOF, a job running during a Redis restart
completes, and a queued job survives the Redis container being recreated (both
verified). `everysec` bounds loss to about a second of writes on a crash; every
key has a TTL, so the AOF stays small. Keep Redis off public networks; it has no
authentication here, which is why compose publishes it on `127.0.0.1` only.

**Next.js server address.** `NEXT_PUBLIC_API_URL` is read only by the Next
server (server-side fetches and the `/api` rewrite); browsers always call
same-origin `/api`. It must be an address reachable *from the web process*. In
the bundled compose file that is `http://api:8000`; `localhost` there would be
the web container itself. It is a build-time value because rewrites are
compiled into the build.

Uploads through that rewrite are allowed up to `AD_MAX_UPLOAD_SIZE_MB` + 1 MB
(read at build time, default 200) via `experimental.proxyClientMaxBodySize`;
above Next's 10 MB default the proxy silently truncates the body and the upload
hangs. Next buffers a proxied body in memory up to that size, so a public
deployment should route `/api/*` to the API at the reverse proxy rather than
through Next.

**Reverse proxy routing (verified with nginx in front of the compose stack).**
Browsers call same-origin `/api/v1/...`, and FastAPI serves exactly that prefix,
so the proxy can send `/api/*` straight to FastAPI with no application change.
With nginx that needs `client_max_body_size 201m`, `proxy_request_buffering off`
(stream uploads instead of spooling them), a `proxy_read_timeout` above the
longest upload, and `X-Forwarded-For $proxy_add_x_forwarded_for` together with
`AD_TRUST_PROXY_HEADERS=true`. In that setup a 40 MB upload went to FastAPI
without touching Next, and the full Playwright suite passed through the proxy.

Scale workers horizontally. They share Redis and a writable storage volume.
If you run more than one API replica, storage must be shared (NFS or an
S3-compatible backend; the local adapter is the current implementation).

## Docker (development)

```bash
docker compose up -d --build
```

The base `docker-compose.yml` is for development: FastAPI (8000) and Next.js
(3000) are published on the host and Redis on `127.0.0.1` only. Images run as
uid 10001. The API image includes FFmpeg. Browser tools are off by default and
the image ships no Chromium; add Playwright to a custom worker image if you
enable them (they report themselves unavailable otherwise).

## Production deployment

```text
Internet ─HTTPS─> Caddy (80/443, the only published ports)
                   ├─ /api/*  -> FastAPI  (api:8000)   -> Redis (AOF) <- worker -> FFmpeg
                   └─ /*      -> Next.js  (web:3000)
```

```bash
AD_DOMAIN=anythingdownload.in \
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` layers these changes onto the base file:

- **Caddy** (`deploy/Caddyfile`) obtains and renews the certificate for
  `AD_DOMAIN`, redirects HTTP to HTTPS, and routes `/api/*` straight to FastAPI,
  so uploads never pass through Next.js. It has no access log (request lines
  carry user-submitted URLs) and its admin API is off.
- **No published ports** for Redis, FastAPI or Next.js (`ports: !reset []`).
- **Production settings**: `AD_ENV=production` (docs off, private targets
  refused at startup), JSON logs, `AD_TRUST_PROXY_HEADERS=true`.
- **Limits on every container**: CPU, memory and PID caps; `no-new-privileges`;
  all capabilities dropped except what Caddy needs to bind 80/443; Docker log
  rotation (10 MB × 3), so container logs cannot fill the disk.
- **Redis** `maxmemory 200mb` with `noeviction`: when full, Redis refuses new
  writes (new jobs fail cleanly) rather than silently evicting job records that
  users are still polling.

`AD_DOMAIN` is required; Compose refuses to start without it.

### Proxy trust and rate limits

Caddy is not configured with `trusted_proxies`, so it ignores any
`X-Forwarded-For` a client sends and sets the header to the connecting address.
The API takes the rightmost entry. Verified through Caddy: 40 requests with a
different forged `X-Forwarded-For` each were limited after 30, exactly like
unforged traffic. **If you put a CDN in front of Caddy**, configure Caddy's
`trusted_proxies` with the CDN's published ranges; otherwise every user shares
the CDN edge's address and is rate limited together.

### Host firewall

Allow inbound TCP 80 and 443 (and UDP 443 for HTTP/3) plus SSH from your
management addresses only. Everything else stays closed; no application port
needs to be reachable from outside the host.

### Secrets

The stack currently needs no secrets: Redis is reachable only on the internal
Docker network, and there are no third-party credentials. If you add any, pass
them through the host environment or Docker secrets. Never commit them, and
do not bake them into images.

### Operational metrics

`/api/v1/metrics` (queue depth, job totals, free storage bytes) is **not served
at the public edge**: Caddy answers 404, because exact free disk space helps time
a storage-exhaustion attempt. Read it from the host instead:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T api \
  python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/metrics').read().decode())"
```

### Sizing the storage guard

The API and worker refuse new uploads and jobs while the storage filesystem has
less than `AD_MIN_FREE_DISK_MB` free (production overlay default 4096). Keep it
above `AD_MAX_FILE_SIZE_MB × AD_MAX_CONCURRENT_JOBS × workers` so work that was
already admitted can finish. `AD_MAX_STORAGE_MB` optionally caps the storage
directory itself. See [security.md](security.md#resource-limits).

## Checklist before going live

- [ ] DNS for `AD_DOMAIN` points at the host; ports 80/443 reachable
- [ ] Deployed with `docker-compose.prod.yml` (no application ports published)
- [ ] Host firewall allows only 80, 443 and management SSH
- [ ] `AD_MIN_FREE_DISK_MB` sized for the host's disk (see above)
- [ ] Storage and Redis volumes on persistent disk, not world-readable
- [ ] `/api/v1/ready` monitored externally; `/api/v1/metrics` read from inside the host
      (see [observability](engineering/observability.md))
- [ ] CI green on the exact revision being deployed
- [ ] Post-deploy check: HTTPS, `/api/v1/ready`, one real job, SSRF refusal

Do not describe a revision as production-ready until those checks have actually
been run against the deployed environment.

## Domain and DNS (GoDaddy)

The domain is registered, but **DNS is not connected to any server yet** (GoDaddy
shows it as *Idle*). Do not create records until a real server exists and its
public address is known. Never point records at `127.0.0.1`, `localhost` or a
private range.

Records to create in GoDaddy (*My Products*, then *DNS*) once the servers exist.
Placeholders are in capitals; replace them with the real addresses:

| Type | Name | Value | TTL | When |
| --- | --- | --- | --- | --- |
| A | `@` | `SERVER_IPV4` | 600 s during rollout, then 1 h | production host exists |
| CNAME | `www` | `anythingdownload.in` | 1 h | only if `www` should work |
| A | `staging` | `STAGING_SERVER_IPV4` | 600 s | staging host exists |
| AAAA | `@` / `staging` | `SERVER_IPV6` | 600 s | **only** if the host really has working IPv6 with 80/443 open |

Notes:

- GoDaddy's default *Parked* `A @` record and any domain *forwarding* must be
  removed or replaced, or traffic still goes to the parking page.
- Keep GoDaddy's nameservers unless you deliberately move DNS (for example a
  hosting provider or CDN that asks for its own nameservers or CNAME targets). If
  a provider specifies different records, use theirs and update this table; the
  only requirement is that each hostname resolves to the host running Caddy.
- `www`: the Caddyfile serves `{$AD_DOMAIN}` only. If `www` gets a record, also
  add it to Caddy, for example a second site block
  `www.{$AD_DOMAIN} { redir https://{$AD_DOMAIN}{uri} permanent }`, so Caddy
  obtains its certificate too.
- **No wildcard record** (`*`) and **no records for internal names** (`redis`,
  `api`, `worker`); those exist only on the Docker network.
- **CAA records are optional.** Add one only to restrict issuance, and then it
  must allow Caddy's CAs (`letsencrypt.org` and `zerossl.com`) or certificates
  will fail to issue.
- Propagation: new records usually resolve within minutes; changed records can
  take up to the previous TTL. Check from outside your network with
  `dig +short anythingdownload.in A` (or `nslookup anythingdownload.in 1.1.1.1`)
  before starting Caddy, so the first ACME attempts do not fail and hit CA rate
  limits.

## HTTPS

Caddy obtains and renews certificates automatically (Let's Encrypt, falling back
to ZeroSSL) once the hostname resolves to the server and ports 80 and 443 are
reachable from the internet. No cron job is needed. Certificates live in the
`caddy-data` volume; keep it, or every redeploy re-issues certificates and can
hit CA rate limits.

## Staging and production runbook

Deploy staging first, on its own server, with the same steps and
`AD_DOMAIN=staging.anythingdownload.in`. Promote to production only after the
smoke tests pass on staging. None of these steps has been executed yet.

### 1. Server preparation

- Ubuntu 24.04 LTS or Debian 12; at least 2 vCPU and 4 GB RAM (the production
  overlay caps containers at about 5 CPU and 4.5 GB in total; size up for heavy
  video use); disk sized for `AD_MIN_FREE_DISK_MB` plus concurrent results.
- A non-root sudo user, SSH keys only (`PasswordAuthentication no`,
  `PermitRootLogin no`), unattended security upgrades enabled.

### 2. Docker

Install Docker Engine and the Compose plugin from Docker's official apt
repository (docs.docker.com/engine/install). Compose **v2.24 or newer** is
required (the optional `env_file` syntax). Check with `docker compose version`.

### 3. Firewall

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from ADMIN_IP to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
```

Docker publishes ports through its own iptables rules, which bypass `ufw`. That
is safe here only because the production overlay publishes nothing except
Caddy's 80 and 443; never add `ports:` to other services. Mirror these rules in
the cloud provider's firewall if it has one.

### 4. DNS

Create the records from *Domain and DNS* and wait until they resolve publicly.

### 5. Environment configuration

```bash
git clone https://github.com/sandeepbollavaram/anything-download.git
cd anything-download
git checkout <the exact reviewed commit>
export AD_DOMAIN=staging.anythingdownload.in    # production: anythingdownload.in
```

Optional overrides go in `.env` (copied from `.env.example`), for example
`AD_MIN_FREE_DISK_MB` sized for the disk. Keep `.env` at mode `600`.

### 6. Secrets

None are required today. If one is added later, keep it on the server only
(host environment or Docker secrets), never in Git, images, logs or this
document.

### 7. Deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
```

Only `caddy` may list published ports.

**Staging only:** keep staging out of search results by adding
`header X-Robots-Tag "noindex, nofollow"` inside the site block of the Caddyfile
on the staging server (a local, uncommitted change), or restrict 80/443 to known
addresses after the certificate has been issued.

### 8. Caddy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs caddy --tail 50
```

Look for `certificate obtained successfully` for `$AD_DOMAIN`.

### 9. HTTPS

```bash
curl -sI http://$AD_DOMAIN/ | head -3     # expect a redirect to https
curl -sI https://$AD_DOMAIN/ | head -1    # expect HTTP/2 200
```

### 10. Health checks

```bash
curl -s https://$AD_DOMAIN/api/v1/health    # {"status":"ok",...}
curl -s https://$AD_DOMAIN/api/v1/ready     # redis, storage and ffmpeg all true
curl -s -o /dev/null -w '%{http_code}\n' https://$AD_DOMAIN/api/v1/metrics   # 404 at the edge
```

Monitor `/api/v1/ready` from outside with an uptime checker every minute.

### 11. Smoke tests

```bash
# SSRF: must be refused with BLOCKED_TARGET
curl -s -X POST https://$AD_DOMAIN/api/v1/analyze -H 'Content-Type: application/json' \
  -d '{"url":"http://169.254.169.254/latest/meta-data/"}'

# A real job end to end
job=$(curl -s -X POST https://$AD_DOMAIN/api/v1/jobs -H 'Content-Type: application/json' \
  -d '{"tool":"qr-generator","input":{"kind":"text","text":"smoke"}}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
sleep 5; curl -s https://$AD_DOMAIN/api/v1/jobs/$job | grep -o '"status":"[A-Z]*"'

# Browser suite from a workstation, against staging only (it exercises rate limits)
PLAYWRIGHT_BASE_URL=https://$AD_DOMAIN E2E_API=1 CI=1 pnpm --filter @anything-download/web test:e2e
```

Then check by hand: the home page, one upload job, one public URL analysis, the
security headers (`curl -sI https://$AD_DOMAIN/`), and the Chrome extension with
its server set to staging.

### 12. Rollback

```bash
git checkout <previous known-good commit>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build --wait
```

Jobs and results live for minutes, so there is no data migration to undo. Keep
the previous images until the new release is confirmed
(`docker image ls "anything-download-*"`).

### 13. Logs

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f api worker
```

Logs are JSON, rotated at 10 MB x 3 per container, and hold no full user URLs.
Caddy has no access log by design.

### 14. Backup and recovery

- **No user data needs backup**: uploads and results delete themselves, and job
  records expire in Redis.
- **Keep `caddy-data`** (certificates and the ACME account) across redeploys;
  losing it only forces re-issuance.
- **Configuration** is Git plus the optional `.env` on the server; record which
  commit is deployed.
- Recovery: rebuild the host, restore `.env` if used, repeat steps 2 to 7.

## Verification status

Last full local verification: 2026-09-15 (release engineering pass).

| Gate | Status | Evidence / what is missing |
| --- | --- | --- |
| Docker images build | Verified locally | dev stack rebuilt; images also built from a clean export of only the committable files |
| Fresh clone without `.env` | Verified locally | clean export: `docker compose config` passes for the base file and the production overlay; the production stack starts |
| Development Compose stack | Verified locally | health, real Redis and FFmpeg jobs, browser suite 46/46 |
| Production overlay | Verified locally | clean export, `AD_DOMAIN=localhost`, host ports 8080/8444: HTTPS via Caddy's local CA, only Caddy publishes ports, docs 404, `/api/v1/metrics` 404 at the edge and 200 inside, security headers present, 10 SSRF probes refused, FFmpeg video to MP3 and QR jobs completed, filename traversal sanitised, MIME detected from content, 256 KB JSON limit (413), forged `X-Forwarded-For` limited after 30 requests, delete removes results |
| Public TLS certificate (ACME) | **Not verified** | needs DNS pointing at a real host |
| Host firewall | **Not verified** | host-specific; follow step 3 |
| DNS | **Not connected** | domain registered with GoDaddy; no records point at a server |
| Staging deployment | **Not deployed** | no server exists yet |
| Production deployment | **Not deployed** | no server exists yet |
| CI | **Not verified** | workflow parses and was reviewed; it has never run (no push) |
