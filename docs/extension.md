# Chrome extension

`apps/extension` is a Manifest V3 companion to the website. It analyzes the page the
user is on through the **existing public API** and hands processing over to the
website. It is not a second downloader backend: the server stays authoritative for
URL validation, SSRF protection, rate limits, restrictions and every other control.

## Architecture

```text
Chrome extension (popup, context menu)
   │  HTTPS, page URL only, no credentials
   ▼
Anything Download API  (/api/v1/analyze)  ── existing validation, SSRF policy, rate limits
   ▼
Website deep link  (/analyze?url=…&tool=…) ── existing tools, jobs, results
```

| Part | File | Role |
| --- | --- | --- |
| Manifest | `src/manifest.json` | permissions, CSP, entry points |
| API client | `src/api.js` | request, timeout, response validation, error classification |
| Capability mapping | `src/capabilities.js` | turns an analysis or failure into what the popup shows |
| Popup | `src/popup/` | current page, Analyze, results, website hand-off |
| Service worker | `src/background.js` | context menu only |
| Options | `src/options/` | server address, theme |

No build step, no bundler, no remote code: the files in `src/` are what ships.

## Features

- **Popup**: shows the current page; on *Analyze this page* lists the public images,
  videos, audio and PDFs the server found, each opening the matching website tool;
  *Open in Anything Download* opens the website analysis.
- **Context menu** (on web pages): Analyze this page, Find images, Find videos, Find
  audio, Find PDFs, Open in Anything Download. A finder opens the popup with that
  request; if Chrome refuses to open the popup, the same request opens on the website.
- **States shown exactly as the server reports them**: supported; login required;
  private; DRM protected; region restricted; live stream; unsupported; private/local
  address (SSRF refusal); rate limited (with a `Retry-After` countdown); service
  unavailable; network failure; timeout; unexpected response; missing permission.
  Restricted and unsupported results never offer a download or finder action.

## API contract

The extension adds **no endpoints**. It uses the same public, versioned API as the
website; any client must treat the server's answer as authoritative.

| Operation | Endpoint | Used by the extension |
| --- | --- | --- |
| Analyze a URL | `POST /api/v1/analyze` `{ "url": … }` → `URLAnalysis` | yes |
| Capabilities / tools | `GET /api/v1/tools`, `GET /api/v1/tools/{id}` | via the analysis `tools` field |
| Client-checkable limits | `GET /api/v1/limits` | not yet (the website uses it) |
| Create a job | `POST /api/v1/jobs` | no, the website does this |
| Job status | `GET /api/v1/jobs/{id}` | no |
| Result | `GET /api/v1/jobs/{id}/result` | no |

Fields the extension relies on, and validates before use: `normalized_url`,
`source_kind` (`direct` \| `webpage` \| `platform`), `resource_type`, `status`
(`ok` \| `unsupported` \| `restricted`), `reason` `{code, message}` when not `ok`,
`tools` (string list) and `resource_counts` (type → non-negative integer). A response
that fails validation is shown as *Unexpected response*, never partially rendered.

Error responses use `{ "error": { "code", "message", "retryable" } }`. The extension
maps `429` to rate limited (reading `Retry-After`), `5xx`, `SERVICE_UNAVAILABLE`,
`QUEUE_FULL` and `STORAGE_FULL` to unavailable, and any other coded error (for
example `BLOCKED_TARGET`, `UNSUPPORTED_SCHEME`, `INVALID_URL`) to a refusal showing
the server's message.

Finder tools used for deep links: `website-image-gallery`, `website-video-finder`,
`website-audio-finder`, `website-pdf-finder` (counts `PDF` + `DOCUMENT`).

## Permissions

| Permission | Why |
| --- | --- |
| `activeTab` | Read the current tab's URL, only after the user clicks the extension or its menu |
| `contextMenus` | The right-click menu |
| `storage` | Theme and server preference (local); a menu request handed to the popup (session, expires after 60 s) |
| `https://anythingdownload.in/*` | Call the API |
| optional `https://*/*`, `http://localhost/*`, `http://127.0.0.1/*` | Requested at runtime **for one origin only**, when the user chooses a self-hosted server |

Not requested: `<all_urls>`, `tabs`, `history`, `cookies`, `webRequest`, `scripting`,
`downloads`, content scripts, web-accessible resources. `tests/unit/manifest.test.mjs`
fails if any of these appear.

Extension pages run under `script-src 'self'; object-src 'none'` with no
`unsafe-eval` or `unsafe-inline`, and load no remote images, fonts or scripts.

## Privacy

- The page address is sent **only when the user chooses an action**. Opening the
  popup sends nothing.
- Requests use `credentials: "omit"`: no cookies or other credentials are sent.
- Browser-internal pages (`chrome://`, `file://`, extension pages) are refused locally
  and never sent.
- No browsing history, page content, analytics, advertising identifiers or tracking.
- Server text is inserted with `textContent` only; the source contains no
  `innerHTML` or other HTML-injection sinks (enforced by a test).

## Security model

The extension inherits the service's hard boundaries: public resources the user is
authorized to use only; no bypass of logins, paywalls, DRM, CAPTCHAs, region
restrictions or any other access control; no private or local network targets; no
credential or cookie access. Extension-side checks (http(s) only, HTTPS server
origin) are usability checks, not security controls. The server decides.

## UI

The popup (360 px) and options page reuse the website's design tokens (warm neutral
surfaces, teal accent), flat colour with no gradients, and the system font stack.
Every text pair meets WCAG AA 4.5:1 in light and dark themes (control borders 3:1);
the link colour has its own token because the dark accent fell below 4.5:1 on its
hover tint. All targets are at least 44 px, focus rings are visible, states use an
icon plus text (never colour alone), errors are announced with `role="alert"`, results
with a polite live region, and motion respects `prefers-reduced-motion`. The theme
follows the system unless set on the options page.

## Testing

```bash
pnpm --filter @anything-download/extension typecheck   # checkJs over src/
pnpm --filter @anything-download/extension test:unit   # node:test: API client, capability mapping, manifest guard
pnpm --filter @anything-download/extension exec playwright install chromium
pnpm --filter @anything-download/extension test:e2e    # unpacked extension in full Chromium, local mock API
EXT_REAL_API_ORIGIN=http://127.0.0.1:8000 pnpm --filter @anything-download/extension test:e2e  # also against a real API
```

Browser tests load the real unpacked extension. They cover popup load, current-URL
detection, the single API request (URL only, no cookie), supported, restricted (login,
DRM), unsupported, SSRF refusal, rate limiting with countdown and retry, API
unavailable, malformed response, network failure, missing permission, HTML-injection
attempt, browser-internal pages, keyboard navigation and focus, accessible names and
44 px targets, dark mode and the theme override, and the context-menu flows. The
optional real-API tests check that a real server refuses a local page and that its
rate limit is surfaced.

**Not covered by automation:** the `activeTab` grant itself. It is issued only by a
real click on the toolbar button, which automation cannot perform, so the test copy of
the manifest adds `tabs`; the shipped manifest does not. Manual check: load unpacked,
open a normal web page, click the toolbar button, confirm the page address appears.

## Installing and publishing

Development: `chrome://extensions` → Developer mode → *Load unpacked* →
`apps/extension/src`. Regenerate icons with `python scripts/make-icons.py` (Pillow).

The extension is **not published**. Publishing to the Chrome Web Store requires a
developer account, the store listing (description, screenshots, the privacy
disclosures above) and Google's review, a manual step for the maintainer.
