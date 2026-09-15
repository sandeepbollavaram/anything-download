# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Open-source project files: issue forms, pull request template, Dependabot
  configuration, README screenshots and badges.

### Changed

- `.cursor/` editor configuration is no longer tracked in the repository.

## [0.1.0] - 2026-09-15

First public release candidate.

### Added

- Website with 38 tools across video, audio, image, PDF, web and utility
  categories, a single analyze workspace, real job progress, result previews and
  automatic deletion.
- FastAPI backend with SSRF-safe fetching, content-based type detection, public
  platform extractors, a Redis job queue, worker and cleanup processes.
- Resource limits for request bodies, uploads, storage, FFmpeg threads, job
  duration and output size.
- Chrome extension (Manifest V3) that analyzes the current page.
- Docker images, a development Compose stack and a production overlay with Caddy
  and automatic HTTPS.
- CI covering API, web, end-to-end tests on the production build, a Docker smoke
  test, image vulnerability scanning, dependency audits and the extension.

[Unreleased]: https://github.com/sandeepbollavaram/anything-download/compare/f6dca9c...HEAD
[0.1.0]: https://github.com/sandeepbollavaram/anything-download/commit/f6dca9c
