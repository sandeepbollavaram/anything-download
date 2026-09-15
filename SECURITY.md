# Security Policy

Anything Download treats every URL and uploaded file as untrusted input.

## Supported versions

Only the latest commit on `main` is supported. There are no long-term release
branches yet.

## What this project will not do

The service is intended for content you are authorized to download or process.
It does **not**:

- bypass authentication, DRM, paywalls, CAPTCHAs, or other access controls
- extract private or members-only accounts
- accept requests to internal, loopback, or link-local addresses (SSRF)
- keep user media indefinitely

If a source cannot be processed legitimately, the API returns a typed error
such as `SOURCE_UNSUPPORTED`, `SOURCE_REQUIRES_AUTH`, or `SOURCE_DRM_PROTECTED`.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Email the maintainer at the address listed on the GitHub profile for
[sandeepbollavaram](https://github.com/sandeepbollavaram), or use GitHub’s
private vulnerability reporting for this repository.

Include:

- a description of the issue
- steps to reproduce
- impact (for example SSRF, path traversal, command injection, data leak)
- whether you have a suggested fix

You should receive an acknowledgement when the report is seen. Please give a
reasonable time to investigate before any public disclosure.

## Operational security notes

- Outbound HTTP is resolved, then connected by pinned IP with Host/SNI of the
  original hostname to reduce DNS rebinding risk.
- Private, reserved, metadata, and single-label hosts are blocked.
- FFmpeg and FFprobe are invoked with argument arrays, never a shell string.
- Temporary files are deleted after success, failure, cancellation, or TTL.
- Production responses never include stack traces.
- Authorization headers, cookies, credentials, and signed query strings are
  not logged.

See `docs/security.md` for the implementation-level checklist.
