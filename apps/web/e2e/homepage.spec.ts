import { expect, test } from "@playwright/test";

test("homepage shows the product and analyze controls", async ({ page }) => {
  await page.goto("/");

  await expect(
    page.getByRole("heading", { name: /Paste anything\.\s*Get exactly what you need\./, level: 1 }),
  ).toBeVisible();
  await expect(page.getByLabel("Paste a URL or upload a file")).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Popular tools" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Video" })).toBeVisible();
});

test("homepage does not overflow horizontally at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  const overflow = await page.evaluate(() => {
    const root = document.documentElement;
    return root.scrollWidth - root.clientWidth;
  });
  expect(overflow).toBeLessThanOrEqual(1);
});

test("homepage offers the optional Chrome extension, which documents its permissions", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Get the Chrome extension" }).click();
  await expect(page).toHaveURL(/\/extension$/);
  await expect(page.getByRole("heading", { name: "Chrome extension", level: 1 })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Permissions it uses" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What it never collects" })).toBeVisible();
  // No fake store link: it is not published yet, and the page says so.
  await expect(page.getByText(/not yet listed on the Chrome Web Store/)).toBeVisible();
  await expect(page.locator('a[href*="chromewebstore.google.com"]')).toHaveCount(0);
});
