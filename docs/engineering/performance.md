# Performance

Implemented constraints (not a benchmark report):

- Analyze uses a streaming GET and sniffs 8 KiB before deciding. It does not
  download an entire video just to classify it.
- Uploads and remote files are written in 64 KiB chunks with a running size cap.
- Jobs never run FFmpeg or large downloads inside the API request thread.
- FFmpeg progress is read from `pipe:1`; stderr is capped at 64 KiB.
- Webpage parse is bounded by `AD_MAX_WEBPAGE_BYTES` and
  `AD_MAX_WEBPAGE_RESOURCES`.
- Homepage is static; analysis is client-side against `/api/v1`.
- Next.js standalone output is used for the web image.

Known limits (NOT VERIFIED with production load):

- One worker process is bounded by `AD_MAX_CONCURRENT_JOBS`.
- Local disk I/O will dominate on large media.
- Multi-replica API needs shared storage or jobs will 404 on the result.
- No CDN, Redis persistence, or horizontal autoscaling is configured here.

Do not treat this file as evidence that the service was load-tested.
