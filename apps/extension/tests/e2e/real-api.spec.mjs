/**
 * Optional: the extension against a real Anything Download API (e.g. the Docker stack).
 * Skipped unless EXT_REAL_API_ORIGIN is set, for example:
 *
 *   EXT_REAL_API_ORIGIN=http://127.0.0.1:8000 pnpm --filter @anything-download/extension test:e2e
 *
 * No third-party sites are involved: the analyzed pages are served locally, which is
 * exactly what the real server must refuse.
 */
import { expect, test } from "@playwright/test";

import { launchWithExtension, startServer } from "./harness.mjs";

const REAL = process.env.EXT_REAL_API_ORIGIN;
test.skip(!REAL, "Set EXT_REAL_API_ORIGIN to run against a real API");
test.describe.configure({ mode: "serial" });

test("real API refuses a private address and the popup shows its reason (SSRF)", async () => {
  const pages = await startServer();
  const ext = await launchWithExtension();
  try {
    await ext.setServer(REAL);
    const { popup } = await ext.openPopupFor(`${pages.origin}/page/ok`);
    await popup.getByRole("button", { name: "Analyze this page" }).click();
    const alert = popup.getByRole("alert");
    await expect(alert.getByRole("heading", { name: "Private or local address" })).toBeVisible({ timeout: 20_000 });
    await expect(alert).toContainText(/private|local|reserved/i);
    await expect(popup.getByRole("list", { name: "Available on this page" }).getByRole("button")).toHaveCount(0);
    expect(pages.analyzed, "the page itself is never fetched through the mock").toHaveLength(0);
  } finally {
    await ext.close();
    await pages.close();
  }
});

test("real API rate limit is surfaced with its Retry-After", async () => {
  const pages = await startServer();
  const ext = await launchWithExtension();
  try {
    // Exhaust the analyze bucket for this client address.
    let limited = false;
    for (let i = 0; i < 80 && !limited; i += 1) {
      const response = await fetch(`${REAL}/api/v1/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: `javascript:probe-${i}` }),
      });
      limited = response.status === 429;
    }
    expect(limited, "the real limiter started refusing").toBe(true);

    await ext.setServer(REAL);
    const { popup } = await ext.openPopupFor(`${pages.origin}/page/ok`);
    await popup.getByRole("button", { name: "Analyze this page" }).click();
    await expect(popup.getByRole("alert").getByRole("heading", { name: "Too many requests" })).toBeVisible();
    await expect(popup.locator("#retry")).toHaveText(/Try again in \d+ s/);
    await expect(popup.locator("#retry")).toBeDisabled();
  } finally {
    await ext.close();
    await pages.close();
  }
});
