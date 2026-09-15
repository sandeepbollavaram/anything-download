/**
 * Test harness: a local mock API + test pages, and a Chromium with the unpacked
 * extension loaded. No third-party sites are contacted.
 *
 * The extension under test is a temporary copy whose manifest differs from the shipped
 * one in two ways only:
 *   - host permission for http://127.0.0.1/* so the popup may call the local mock API;
 *   - the "tabs" permission, because `activeTab` is granted by a real user click on the
 *     toolbar button, which automation cannot perform. The shipped manifest does not
 *     request "tabs" (tests/unit/manifest.test.mjs enforces that).
 */
import { chromium } from "@playwright/test";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../../src/", import.meta.url));

const WEBPAGE = {
  normalized_url: "",
  source_kind: "webpage",
  resource_type: "WEBPAGE",
  status: "ok",
  title: "Field notes",
  tools: ["website-image-gallery", "website-video-finder", "website-audio-finder", "website-pdf-finder"],
  resource_counts: { IMAGE: 6, VIDEO: 2, PDF: 1 },
};

/** Mock /api/v1/analyze responses, chosen by the path of the analyzed page. */
const SCENARIOS = {
  "/page/ok": () => [200, WEBPAGE],
  "/page/restricted": () => [
    200,
    { ...WEBPAGE, status: "restricted", tools: [], reason: { code: "SOURCE_REQUIRES_AUTH", message: "This content requires signing in." } },
  ],
  "/page/drm": () => [
    200,
    { ...WEBPAGE, status: "restricted", tools: [], reason: { code: "SOURCE_DRM_PROTECTED", message: "This media is DRM protected." } },
  ],
  "/page/unsupported": () => [
    200,
    { ...WEBPAGE, status: "unsupported", tools: [], reason: { code: "SOURCE_UNSUPPORTED", message: "This source is not supported." } },
  ],
  "/page/blocked": () => [
    400,
    { error: { code: "BLOCKED_TARGET", message: "URLs pointing to private, local or reserved network addresses cannot be processed." } },
  ],
  "/page/ratelimit": () => [429, { error: { code: "RATE_LIMITED", message: "Too many requests." } }, { "Retry-After": "3" }],
  "/page/unavailable": () => [503, "Service Unavailable", { "Content-Type": "text/plain" }],
  "/page/malformed": () => [200, { status: "ok" }],
  "/page/xss": () => [200, { ...WEBPAGE, title: '<img src=x onerror="document.title=\'pwned\'">' }],
};

export async function startServer() {
  const analyzed = [];
  const server = createServer((req, res) => {
    const url = new URL(req.url ?? "/", "http://127.0.0.1");
    if (url.pathname === "/api/v1/analyze" && req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", () => {
        const requested = JSON.parse(body || "{}").url ?? "";
        analyzed.push({ url: requested, cookie: req.headers.cookie ?? null });
        const scenario = SCENARIOS[new URL(requested).pathname] ?? SCENARIOS["/page/ok"];
        const [status, payload, headers = {}] = scenario();
        const text = typeof payload === "string" ? payload : JSON.stringify({ ...payload, normalized_url: requested });
        res.writeHead(status, { "Content-Type": "application/json", ...headers });
        res.end(text);
      });
      return;
    }
    // Test pages and the website's /analyze deep-link target.
    res.writeHead(200, { "Content-Type": "text/html", "Set-Cookie": "session=secret-cookie; Path=/" });
    res.end(`<!doctype html><title>${url.pathname}</title><h1>${url.pathname}</h1>`);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
  return { origin: `http://127.0.0.1:${port}`, analyzed, close: () => new Promise((r) => server.close(r)) };
}

export async function launchWithExtension({ colorScheme = "light" } = {}) {
  const extensionDir = mkdtempSync(join(tmpdir(), "ad-extension-"));
  cpSync(SRC, extensionDir, { recursive: true });
  const manifestPath = join(extensionDir, "manifest.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
  manifest.host_permissions = [...manifest.host_permissions, "http://127.0.0.1/*"];
  manifest.permissions = [...manifest.permissions, "tabs"];
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2));

  const userDataDir = mkdtempSync(join(tmpdir(), "ad-extension-profile-"));
  const context = await chromium.launchPersistentContext(userDataDir, {
    channel: "chromium",
    headless: !process.env.HEADED,
    colorScheme,
    args: [`--disable-extensions-except=${extensionDir}`, `--load-extension=${extensionDir}`],
  });
  const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent("serviceworker"));
  const extensionId = new URL(worker.url()).host;

  return {
    context,
    worker,
    extensionId,
    /** Point the extension at a server origin (as the options page would). */
    async setServer(origin) {
      await worker.evaluate((value) => chrome.storage.local.set({ serverOrigin: value }), origin);
    },
    /** Open a web page in a tab, then the popup for that tab. */
    async openPopupFor(pageUrl) {
      const tab = await context.newPage();
      await tab.goto(pageUrl);
      const tabId = await worker.evaluate(async (url) => (await chrome.tabs.query({})).find((t) => t.url === url)?.id, pageUrl);
      const popup = await context.newPage();
      await popup.goto(`chrome-extension://${extensionId}/popup/popup.html?tabId=${tabId}`);
      return { tab, popup };
    },
    async close() {
      await context.close();
      rmSync(userDataDir, { recursive: true, force: true });
      rmSync(extensionDir, { recursive: true, force: true });
    },
  };
}
