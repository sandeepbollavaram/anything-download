import assert from "node:assert/strict";
import { test } from "node:test";

import { ApiFailure } from "../../src/api.js";
import { analyzablePageUrl, describeAnalysis, describeFailure, siteLink } from "../../src/capabilities.js";
import { normalizeServerOrigin } from "../../src/config.js";

const webpage = (overrides = {}) => ({
  normalized_url: "https://site.example/a",
  source_kind: "webpage",
  resource_type: "WEBPAGE",
  status: "ok",
  title: "A page",
  tools: ["website-image-gallery", "website-video-finder", "website-audio-finder", "website-pdf-finder"],
  resource_counts: { IMAGE: 4, VIDEO: 1, PDF: 1, DOCUMENT: 2 },
  ...overrides,
});

test("webpage: one action per resource kind the server found and offered", () => {
  const view = describeAnalysis(webpage());
  assert.equal(view.tone, "success");
  assert.deepEqual(
    view.actions.map((a) => [a.id, a.tool, a.count]),
    [
      ["images", "website-image-gallery", 4],
      ["videos", "website-video-finder", 1],
      ["pdfs", "website-pdf-finder", 3],
    ],
  );
  assert.match(view.message, /4 images, 1 videos, 3 PDFs/);
});

test("no action is offered for a tool the server did not list", () => {
  const view = describeAnalysis(webpage({ tools: ["website-video-finder"] }));
  assert.deepEqual(
    view.actions.map((a) => a.id),
    ["videos"],
  );
});

test("context-menu focus moves the requested finder first, or explains its absence", () => {
  assert.equal(describeAnalysis(webpage(), "pdfs").actions[0].id, "pdfs");
  const view = describeAnalysis(webpage({ resource_counts: { IMAGE: 2 } }), "videos");
  assert.equal(view.actions.length, 1);
  assert.match(view.detail, /No videos were found/);
});

test("restricted sources show the server's reason and never an action", () => {
  for (const [code, label] of [
    ["SOURCE_REQUIRES_AUTH", "Login required"],
    ["SOURCE_DRM_PROTECTED", "DRM protected"],
    ["SOURCE_PRIVATE", "Private content"],
    ["SOURCE_GEO_RESTRICTED", "Not available in this region"],
  ]) {
    const view = describeAnalysis(
      webpage({ status: "restricted", tools: ["website-image-gallery"], reason: { code, message: `server says ${code}` } }),
    );
    assert.equal(view.heading, label);
    assert.equal(view.message, `server says ${code}`);
    assert.equal(view.tone, "warning");
    assert.deepEqual(view.actions, [], "no download action for restricted content");
    assert.equal(view.openSite, false);
  }
});

test("unsupported sources are informational with no actions", () => {
  const view = describeAnalysis(
    webpage({ status: "unsupported", tools: [], reason: { code: "SOURCE_UNSUPPORTED", message: "Not a supported source." } }),
  );
  assert.equal(view.heading, "Not supported");
  assert.deepEqual(view.actions, []);
});

test("failures map to honest, recoverable states", () => {
  const blocked = describeFailure(new ApiFailure("rejected", "Blocked by server.", { code: "BLOCKED_TARGET" }));
  assert.equal(blocked.heading, "Private or local address");
  assert.equal(blocked.retryable, false);

  const limited = describeFailure(new ApiFailure("rate_limited", "Slow down.", { retryAfterSeconds: 9 }));
  assert.equal(limited.retryAfterSeconds, 9);
  assert.equal(limited.retryable, true);

  for (const kind of ["network", "timeout", "unavailable", "malformed"]) {
    const view = describeFailure(new ApiFailure(kind, "x"));
    assert.equal(view.tone, "error");
    assert.equal(view.retryable, true, kind);
    assert.deepEqual(view.actions, []);
  }
  assert.equal(describeFailure(new ApiFailure("permission", "no")).heading, "Permission needed");
});

test("only http(s) pages are analyzable; browser pages are never sent", () => {
  assert.equal(analyzablePageUrl("https://a.example/x?y=1"), "https://a.example/x?y=1");
  for (const url of ["chrome://settings", "chrome-extension://abc/popup.html", "file:///etc/passwd", "about:blank", "javascript:alert(1)", "", null, "not a url"]) {
    assert.equal(analyzablePageUrl(url), null, String(url));
  }
});

test("site deep links encode the page URL", () => {
  const link = siteLink("https://anythingdownload.in", "https://a.example/p?q=1&r=<x>", "website-pdf-finder");
  const parsed = new URL(link);
  assert.equal(parsed.origin, "https://anythingdownload.in");
  assert.equal(parsed.pathname, "/analyze");
  assert.equal(parsed.searchParams.get("url"), "https://a.example/p?q=1&r=<x>");
  assert.equal(parsed.searchParams.get("tool"), "website-pdf-finder");
});

test("server origin setting requires HTTPS except for localhost", () => {
  assert.equal(normalizeServerOrigin("https://my.server.example/some/path"), "https://my.server.example");
  assert.equal(normalizeServerOrigin("http://localhost:8000"), "http://localhost:8000");
  assert.equal(normalizeServerOrigin("http://127.0.0.1:3000/"), "http://127.0.0.1:3000");
  for (const bad of ["http://my.server.example", "ftp://x.example", "https://user:pw@x.example", "javascript:alert(1)", "nope"]) {
    assert.equal(normalizeServerOrigin(bad), null, bad);
  }
});
