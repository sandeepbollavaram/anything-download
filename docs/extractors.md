# Extractors

Extractors classify a URL and, when asked, fetch a file.

## Families

### Direct (`extractors/direct.py`)

Used when the URL is not a known platform. A streaming GET is issued. The
first 8 KiB are sniffed. Headers (`Content-Type`, `Content-Length`,
`Content-Disposition`) are hints only.

### Generic webpage (`extractors/generic_webpage.py`)

If the body is HTML, the parser collects publicly referenced resources from:

- `img`, `video`, `audio`, `source`, `a[href]`
- Open Graph and Twitter card images
- `link` icons
- JSON-LD media URLs when they are plain strings

It does not execute JavaScript. Page size and resource count are capped.

### Platforms (`extractors/platforms/`)

Plugin extractors implement `PlatformExtractor`:

- `detect(parsed)`
- `analyze(url, settings)`
- `download(...)`
- `restrictions()`

Registered platforms: YouTube, Vimeo, Dailymotion, Reddit, TikTok, Twitch,
Instagram, Facebook.

They share `ytdlp_base.py`. yt-dlp is configured with:

- no cookies, no browser cookie import, no credentials
- `geo_bypass=False`
- playlists reduced to the first item
- only formats the source lists

Error text is mapped to typed codes (`SOURCE_DRM_PROTECTED`,
`SOURCE_PRIVATE`, `SOURCE_REQUIRES_AUTH`, `SOURCE_LIVE_STREAM`,
`SOURCE_GEO_RESTRICTED`, `SOURCE_UNSUPPORTED`, …).

If yt-dlp cannot extract a public listing, the analyzer returns
`status=unsupported` or `restricted` with a reason. The UI must not show a
download action in that case.

## Adding a platform

1. Create `extractors/platforms/<name>.py` with host detection and any path
   refinement.
2. Register it in `extractors/registry.py`.
3. Add fixture-based unit tests. Do not hit the live site in default CI.
4. Document limitations in the extractor’s `restrictions()`.

## Verification

| Item | Status |
| --- | --- |
| Direct file + generic webpage extraction | Implemented; unit/integration tested with fixtures |
| Platform extractors (yt-dlp, no cookies/geo-bypass) | Implemented; **live sites NOT VERIFIED** in default CI |
| Browser tools gated + hidden when unavailable | Implemented |
