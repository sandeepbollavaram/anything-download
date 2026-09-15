import { expect, test, type Page } from "@playwright/test";
import { Buffer } from "node:buffer";

/** Next.js injects an always-empty role="alert" route announcer; exclude it. */
function statusMessage(page: Page) {
  return page.locator(
    '[role="alert"]:not(#__next-route-announcer__), [role="status"]:not(.sr-only)',
  );
}

/** "Download" also matches the "Anything Download" wordmark link in the header. */
function downloadLink(page: Page) {
  return page.getByRole("link", { name: "Download", exact: true });
}

test.describe("API-backed flows", () => {
  test.skip(!process.env.E2E_API, "Requires a local API (set E2E_API=1 in CI)");

  test("javascript: URLs do not offer a download", async ({ page }) => {
    await page.goto("/analyze?url=" + encodeURIComponent("javascript:alert(1)"));
    await expect(statusMessage(page).first()).toContainText(
      /can't process|not valid|unsupported|blocked|scheme/i,
      { timeout: 20_000 },
    );
    await expect(downloadLink(page)).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Download", exact: true })).toHaveCount(0);
  });

  test("loopback URLs are blocked", async ({ page }) => {
    await page.goto("/analyze?url=" + encodeURIComponent("http://127.0.0.1/secret"));
    await expect(statusMessage(page).first()).toContainText(
      /can't process|blocked|private|not allowed|unsupported/i,
      { timeout: 20_000 },
    );
    await expect(downloadLink(page)).toHaveCount(0);
  });

  test("upload, process, and download a PNG as WebP", async ({ page }) => {
    // Processing waits are longer than the default per-test timeout.
    test.setTimeout(120_000);
    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      "base64",
    );
    await page.goto("/tools/image-to-webp");
    const chooser = page.getByLabel(/choose file/i).or(page.locator('input[type="file"]'));
    await chooser.setInputFiles({ name: "pixel.png", mimeType: "image/png", buffer: png });
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(
      page.getByText(/image-to-webp|Image to WebP|Available operations/i).first(),
    ).toBeVisible({ timeout: 20_000 });
    await page.getByRole("button", { name: "Start" }).click();
    await expect(page.getByRole("heading", { name: /your result/i })).toBeVisible({
      timeout: 60_000,
    });
    const downloadPromise = page.waitForEvent("download");
    await downloadLink(page).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename().toLowerCase()).toMatch(/\.webp$/);
  });

  test("uploads larger than 10 MB pass through the web proxy", async ({ page }) => {
    // Next's /api rewrite proxy truncates bodies above 10 MB by default, which made
    // every such upload hang for 30 s and then fail. Only the upload is exercised:
    // the file is a valid MP4 header followed by padding, so it is never processed.
    test.setTimeout(120_000);
    const header = Buffer.from(
      "00000020667479706973736f6d00000200697373306d697332617663316d703431",
      "hex",
    );
    const mp4 = Buffer.concat([header, Buffer.alloc(12 * 1024 * 1024)]);
    await page.goto("/tools/video-to-mp3");
    const uploadResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/v1/uploads") && response.request().method() === "POST",
      { timeout: 60_000 },
    );
    await page
      .locator('input[type="file"]')
      .setInputFiles({ name: "padded.mp4", mimeType: "video/mp4", buffer: mp4 });
    await page.getByRole("button", { name: "Analyze" }).click();
    expect((await uploadResponse).status()).toBe(201);
    await expect(page.getByRole("button", { name: "Start" })).toBeVisible({ timeout: 20_000 });
  });

  test("files over the published upload limit are refused before uploading", async ({ page }) => {
    // A 200 MB file is impractical in a test, so the limit itself is lowered.
    await page.route("**/api/v1/limits", (route) =>
      route.fulfill({
        json: {
          max_upload_bytes: 1024 * 1024,
          max_file_bytes: 500 * 1024 * 1024,
          max_url_length: 2048,
          max_text_chars: 10000,
          max_files_per_job: 50,
          result_ttl_seconds: 1800,
          upload_ttl_seconds: 1800,
        },
      }),
    );
    let uploadRequests = 0;
    page.on("request", (request) => {
      if (request.url().includes("/api/v1/uploads") && request.method() === "POST") {
        uploadRequests += 1;
      }
    });
    await page.goto("/tools/video-to-mp3");
    await page.locator('input[type="file"]').setInputFiles({
      name: "too-big.mp4",
      mimeType: "video/mp4",
      buffer: Buffer.alloc(2 * 1024 * 1024),
    });
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(statusMessage(page).first()).toContainText(/limited to 1(\.0)? MB/i);
    expect(uploadRequests).toBe(0);
  });

  test("QR generator produces a downloadable PNG", async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto("/tools/qr-generator");
    await page.getByLabel(/text or url to encode/i).fill("https://example.com/e2e");
    await page.getByRole("button", { name: "Start" }).click();
    await expect(page.getByRole("heading", { name: /your result/i })).toBeVisible({
      timeout: 60_000,
    });
    await expect(downloadLink(page)).toBeVisible();
    await expect(downloadLink(page)).toHaveAttribute("download", /\.png$/i);
  });
});
