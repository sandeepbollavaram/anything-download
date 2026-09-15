import { expect, test } from "@playwright/test";

import { launchWithExtension, startServer } from "./harness.mjs";

/** @type {Awaited<ReturnType<typeof startServer>>} */
let server;
/** @type {Awaited<ReturnType<typeof launchWithExtension>>} */
let ext;

test.beforeEach(async () => {
  server = await startServer();
  ext = await launchWithExtension();
  await ext.setServer(server.origin);
});

test.afterEach(async () => {
  await ext.close();
  await server.close();
});

const resultPanel = (popup) => popup.locator("#panel");

test("popup loads, shows the current page, and sends nothing until asked", async () => {
  const pageUrl = `${server.origin}/page/ok`;
  const { popup } = await ext.openPopupFor(pageUrl);
  await expect(popup.getByRole("heading", { name: "Current page" })).toBeVisible();
  await expect(popup.locator("#page-host")).toHaveText("127.0.0.1");
  await expect(popup.locator("#page-url")).toHaveText(pageUrl);
  await expect(popup.getByRole("button", { name: "Analyze this page" })).toBeEnabled();
  await popup.waitForTimeout(500);
  expect(server.analyzed).toHaveLength(0);
});

test("supported page: one request with the page URL only, finders from the server's answer", async () => {
  const pageUrl = `${server.origin}/page/ok`;
  const { popup } = await ext.openPopupFor(pageUrl);
  await popup.getByRole("button", { name: "Analyze this page" }).click();

  await expect(resultPanel(popup).getByRole("heading", { name: "Field notes" })).toBeVisible();
  await expect(popup.getByText("Found 6 images, 2 videos, 1 PDFs.")).toBeVisible();
  await expect(popup.locator("#skeleton"), "loading placeholder is gone once the result shows").toBeHidden();
  await expect(popup.locator("#result")).toHaveAttribute("aria-busy", "false");
  const actions = popup.getByRole("list", { name: "Available on this page" }).getByRole("button");
  await expect(actions).toHaveCount(3);
  await expect(actions.nth(0)).toHaveAccessibleName("Find images: 6 found. Opens in Anything Download.");
  // Audio was offered as a tool but none was found: no empty action.
  await expect(popup.getByRole("button", { name: /Find audio/ })).toHaveCount(0);

  expect(server.analyzed).toEqual([{ url: pageUrl, cookie: null }]);

  const opened = ext.context.waitForEvent("page");
  await actions.nth(0).click();
  const site = new URL((await opened).url());
  expect(site.origin).toBe(server.origin);
  expect(site.pathname).toBe("/analyze");
  expect(site.searchParams.get("url")).toBe(pageUrl);
  expect(site.searchParams.get("tool")).toBe("website-image-gallery");
});

for (const [path, heading, message] of [
  ["/page/restricted", "Login required", "This content requires signing in."],
  ["/page/drm", "DRM protected", "This media is DRM protected."],
]) {
  test(`restricted (${heading}): exact reason, no download action`, async () => {
    const { popup } = await ext.openPopupFor(`${server.origin}${path}`);
    await popup.getByRole("button", { name: "Analyze this page" }).click();
    const alert = popup.getByRole("alert");
    await expect(alert.getByRole("heading", { name: heading })).toBeVisible();
    await expect(alert).toContainText(message);
    await expect(popup.getByRole("list", { name: "Available on this page" }).getByRole("button")).toHaveCount(0);
    // "Open in Anything Download" stays available; no download or finder action may appear.
    await expect(popup.getByRole("button", { name: /^(download|find)/i })).toHaveCount(0);
  });
}

test("unsupported page", async () => {
  const { popup } = await ext.openPopupFor(`${server.origin}/page/unsupported`);
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  await expect(popup.getByRole("status").getByRole("heading", { name: "Not supported" })).toBeVisible();
  await expect(popup.getByText("This source is not supported.")).toBeVisible();
});

test("server SSRF rejection is shown as the server reported it", async () => {
  const { popup } = await ext.openPopupFor(`${server.origin}/page/blocked`);
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  const alert = popup.getByRole("alert");
  await expect(alert.getByRole("heading", { name: "Private or local address" })).toBeVisible();
  await expect(alert).toContainText("private, local or reserved network addresses");
  await expect(popup.getByRole("button", { name: "Try again" })).toBeHidden();
});

test("rate limited: Retry-After countdown, then retry", async () => {
  const { popup } = await ext.openPopupFor(`${server.origin}/page/ratelimit`);
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  await expect(popup.getByRole("alert").getByRole("heading", { name: "Too many requests" })).toBeVisible();
  const retry = popup.locator("#retry");
  await expect(retry).toBeDisabled();
  await expect(retry).toHaveText(/Try again in [1-3] s/);
  await expect(retry).toBeEnabled({ timeout: 6_000 });
  await retry.click();
  await expect.poll(() => server.analyzed.length).toBe(2);
});

test("API unavailable and malformed responses", async () => {
  let { popup } = await ext.openPopupFor(`${server.origin}/page/unavailable`);
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  await expect(popup.getByRole("alert").getByRole("heading", { name: "Service unavailable" })).toBeVisible();
  await expect(popup.getByRole("button", { name: "Try again" })).toBeVisible();

  ({ popup } = await ext.openPopupFor(`${server.origin}/page/malformed`));
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  await expect(popup.getByRole("alert").getByRole("heading", { name: "Unexpected response" })).toBeVisible();
  await expect(popup.getByRole("list", { name: "Available on this page" }).getByRole("button")).toHaveCount(0);
});

test("network failure", async () => {
  const closed = "http://127.0.0.1:9"; // discard port: nothing listens
  await ext.setServer(closed);
  const { popup } = await ext.openPopupFor(`${server.origin}/page/ok`);
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  await expect(popup.getByRole("alert").getByRole("heading", { name: "Can't reach Anything Download" })).toBeVisible();
});

test("missing host permission is reported instead of silently failing", async () => {
  await ext.setServer("https://not-granted.example");
  const { popup } = await ext.openPopupFor(`${server.origin}/page/ok`);
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  await expect(popup.getByRole("alert").getByRole("heading", { name: "Permission needed" })).toBeVisible();
  expect(server.analyzed).toHaveLength(0);
});

test("server text is rendered as text, never as HTML", async () => {
  const { popup } = await ext.openPopupFor(`${server.origin}/page/xss`);
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  await expect(resultPanel(popup).locator("#heading")).toHaveText('<img src=x onerror="document.title=\'pwned\'">');
  await expect(popup.locator("#panel img")).toHaveCount(0);
  expect(await popup.title()).toBe("Anything Download");
});

test("browser-internal pages are refused locally and never sent", async () => {
  const popup = await ext.context.newPage();
  await popup.goto(`chrome-extension://${ext.extensionId}/popup/popup.html`);
  // The active tab here is the extension page itself.
  await expect(popup.locator("#page-host")).toHaveText("This page can't be analyzed");
  await expect(popup.getByRole("button", { name: "Analyze this page" })).toBeDisabled();
  await expect(popup.getByRole("button", { name: "Open in Anything Download" })).toBeDisabled();
  expect(server.analyzed).toHaveLength(0);
});

test("keyboard: every control is reachable and operable with a visible focus ring", async () => {
  const { popup } = await ext.openPopupFor(`${server.origin}/page/ok`);
  await popup.keyboard.press("Tab");
  await expect(popup.getByRole("button", { name: "Extension settings" })).toBeFocused();
  await popup.keyboard.press("Tab");
  const analyze = popup.getByRole("button", { name: "Analyze this page" });
  await expect(analyze).toBeFocused();
  const outline = await analyze.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
  await popup.keyboard.press("Enter");
  await expect(popup.getByText("Found 6 images, 2 videos, 1 PDFs.")).toBeVisible();
  await popup.keyboard.press("Tab");
  await expect(popup.getByRole("button", { name: /Find images/ })).toBeFocused();
});

test("accessibility: named controls, 44px targets, announced results", async () => {
  const { popup } = await ext.openPopupFor(`${server.origin}/page/ok`);
  await popup.getByRole("button", { name: "Analyze this page" }).click();
  await expect(popup.getByRole("status")).toBeVisible();
  for (const button of await popup.getByRole("button").all()) {
    if (!(await button.isVisible())) {
      continue;
    }
    const name = (await button.getAttribute("aria-label")) ?? (await button.innerText());
    expect(name.trim().length, "every button has an accessible name").toBeGreaterThan(0);
    const box = await button.boundingBox();
    expect(box.height, `${name} is at least 44px tall`).toBeGreaterThanOrEqual(44);
  }
  await expect(popup.locator("#result")).toHaveAttribute("aria-live", "polite");
  await expect(popup.locator("html")).toHaveAttribute("lang", "en");
});

test("dark mode follows the system, and the saved theme overrides it", async () => {
  await ext.close();
  ext = await launchWithExtension({ colorScheme: "dark" });
  await ext.setServer(server.origin);
  let { popup } = await ext.openPopupFor(`${server.origin}/page/ok`);
  const background = () => popup.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(await background()).toBe("rgb(5, 11, 25)"); // --background, dark (#050b19)

  await ext.worker.evaluate(() => chrome.storage.local.set({ theme: "light" }));
  ({ popup } = await ext.openPopupFor(`${server.origin}/page/ok`));
  expect(await background()).toBe("rgb(245, 247, 251)"); // --background, light (#f5f7fb)
});

test("context menu: a finder either opens the popup with the request or continues on the website", async () => {
  const pageUrl = `${server.origin}/page/ok`;
  await ext.worker.evaluate((url) => globalThis.handleMenuClick("anything-download:videos", url), pageUrl);
  // Which path Chromium takes depends on window focus: chrome.action.openPopup() may
  // succeed (the request waits in session storage) or be refused (a website tab opens).
  const snapshot = () =>
    ext.worker.evaluate(async () => ({
      pending: (await chrome.storage.session.get("pendingAction")).pendingAction ?? null,
      tabs: (await chrome.tabs.query({})).map((t) => t.url ?? ""),
    }));
  let state = await snapshot();
  for (let i = 0; i < 50 && !state.pending && !state.tabs.some((u) => u.includes("/analyze?")); i += 1) {
    await new Promise((r) => setTimeout(r, 100));
    state = await snapshot();
  }
  const { pending, tabs } = state;
  if (pending) {
    expect(pending.pageUrl).toBe(pageUrl);
    expect(pending.focus).toBe("videos");
  } else {
    const site = new URL(tabs.find((u) => u.includes("/analyze?")));
    expect(site.searchParams.get("url")).toBe(pageUrl);
    expect(site.searchParams.get("tool")).toBe("website-video-finder");
  }
});

test("context menu: 'Open in Anything Download' opens the website without calling the API", async () => {
  const pageUrl = `${server.origin}/page/ok`;
  await ext.worker.evaluate((url) => globalThis.handleMenuClick("anything-download:open", url), pageUrl);
  await expect
    .poll(() => ext.worker.evaluate(async () => (await chrome.tabs.query({})).map((t) => t.url ?? "")))
    .toContainEqual(`${server.origin}/analyze?url=${encodeURIComponent(pageUrl)}`);
  expect(server.analyzed).toHaveLength(0);
});

test("context menu ignores browser-internal pages", async () => {
  const before = await ext.worker.evaluate(async () => (await chrome.tabs.query({})).length);
  await ext.worker.evaluate(() => globalThis.handleMenuClick("anything-download:analyze", "chrome://settings"));
  const pending = await ext.worker.evaluate(async () => (await chrome.storage.session.get("pendingAction")).pendingAction);
  expect(pending).toBeUndefined();
  expect(await ext.worker.evaluate(async () => (await chrome.tabs.query({})).length)).toBe(before);
});

test("context menu request is picked up by the popup and runs the chosen finder first", async () => {
  const pageUrl = `${server.origin}/page/ok`;
  await ext.worker.evaluate(
    (url) => chrome.storage.session.set({ pendingAction: { pageUrl: url, focus: "pdfs", createdAt: Date.now() } }),
    pageUrl,
  );
  const popup = await ext.context.newPage();
  await popup.goto(`chrome-extension://${ext.extensionId}/popup/popup.html`);
  const actions = popup.getByRole("list", { name: "Available on this page" }).getByRole("button");
  await expect(actions.first()).toHaveAccessibleName(/^Find PDFs/);
  expect(server.analyzed.map((a) => a.url)).toEqual([pageUrl]);
  // Consumed once: reopening does not re-send the page.
  const again = await ext.context.newPage();
  await again.goto(`chrome-extension://${ext.extensionId}/popup/popup.html`);
  await again.waitForTimeout(500);
  expect(server.analyzed).toHaveLength(1);
});

test("stale context-menu requests are ignored", async () => {
  await ext.worker.evaluate(
    (url) => chrome.storage.session.set({ pendingAction: { pageUrl: url, focus: null, createdAt: Date.now() - 5 * 60_000 } }),
    `${server.origin}/page/ok`,
  );
  const popup = await ext.context.newPage();
  await popup.goto(`chrome-extension://${ext.extensionId}/popup/popup.html`);
  await popup.waitForTimeout(500);
  expect(server.analyzed).toHaveLength(0);
});
