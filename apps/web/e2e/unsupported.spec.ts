import { expect, test } from "@playwright/test";

test.describe("unsupported sources", () => {
  test.skip(!process.env.E2E_API, "API-dependent tests require E2E_API");

  // The rejection text is rendered twice on purpose: once in a visible panel and
  // once in an sr-only live region. Assert on the visible one.
  const visibleMessage = (page: import("@playwright/test").Page, pattern: RegExp) =>
    page.locator('[role="alert"]:not(#__next-route-announcer__)').filter({ hasText: pattern });

  // "Download" alone also matches the "Anything Download" wordmark in the header.
  const downloadLink = (page: import("@playwright/test").Page) =>
    page.getByRole("link", { name: "Download", exact: true });

  test("javascript: URLs do not offer a download", async ({ page }) => {
    await page.goto("/analyze?url=" + encodeURIComponent("javascript:alert(1)"));

    await expect(
      visibleMessage(page, /can't process this source|not valid|unsupported|blocked|scheme/i).first(),
    ).toBeVisible({ timeout: 20_000 });
    await expect(downloadLink(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Download", exact: true })).toHaveCount(0);
  });

  test("loopback URLs do not offer a download", async ({ page }) => {
    await page.goto("/analyze?url=" + encodeURIComponent("http://127.0.0.1/"));

    await expect(
      visibleMessage(
        page,
        /can't process this source|blocked|not allowed|unsupported|private/i,
      ).first(),
    ).toBeVisible({ timeout: 20_000 });
    await expect(downloadLink(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Download", exact: true })).toHaveCount(0);
  });
});
