import { expect, test } from "@playwright/test";

const slugs = [
  "video-downloader",
  "image-compressor",
  "pdf-compressor",
  "audio-converter",
  "url-analyzer",
  "qr-generator",
];

test("tools index renders", async ({ page }) => {
  await page.goto("/tools");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
});

for (const slug of slugs) {
  test(`/tools/${slug} has a heading and no download button before work`, async ({ page }) => {
    await page.goto(`/tools/${slug}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download", exact: true })).toHaveCount(0);
  });
}
