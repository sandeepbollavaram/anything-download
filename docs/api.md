# API

Base path: `/api/v1`

OpenAPI is served at `/api/v1/openapi.json` and Swagger UI at `/api/v1/docs`
when `AD_ENABLE_DOCS=true`.

All errors use:

```json
{
  "error": {
    "code": "SOURCE_UNSUPPORTED",
    "message": "This source is currently unsupported.",
    "retryable": false
  }
}
```

Codes are defined in `anything_download.errors.ErrorCode`.

## Endpoints

### `POST /analyze`

Body: `{ "url": "https://example.com/file.pdf" }`

Returns `URLAnalysis`. Source problems are in `status` / `reason` (HTTP 200).
Malformed or blocked URLs are HTTP 400/414.

### `POST /jobs`

Body:

```json
{
  "tool": "image-compressor",
  "input": { "kind": "url", "url": "https://example.com/a.png" },
  "options": { "quality": 75 }
}
```

`input.kind` is `url` | `upload` | `uploads` | `text`.

### `GET /jobs/{id}`

Public job view. Does not include the source URL.

### `GET /jobs/{id}/result`

File download. `410` if expired.

### `POST /uploads`

Raw body (`application/octet-stream`). Header `X-File-Name` is
percent-encoded UTF-8. Optional `X-File-Type`.

### `GET /tools` and `GET /tools/{id}`

Catalogue with JSON Schema for options and `available` / `missing_requirements`.

### `GET /health`

Liveness.

### `GET /ready`

Readiness. `503` if Redis or storage is down. FFmpeg is reported but does not
fail readiness (the API can still analyze URLs).

### `GET /metrics`

Operational counters. No per-user content. Internal only: the production Caddy
edge answers 404 for this path.

## Rate limits

429 with `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`.

## Verification

| Item | Status |
| --- | --- |
| Pydantic validation, typed errors, rate limits | Implemented |
| Docs off when `AD_ENABLE_DOCS` is not enabled in production | Implemented |
| Stack traces hidden when `AD_ENV=production` | Implemented |
| Live production traffic / OpenAPI review on the public host | **NOT VERIFIED** |
