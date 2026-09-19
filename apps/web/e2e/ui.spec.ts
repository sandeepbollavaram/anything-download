import { expect, test, type Page } from "@playwright/test";
import { Buffer } from "node:buffer";

/** Next.js injects an always-empty role="alert" route announcer; exclude it. */
const alerts = (page: Page) => page.locator('[role="alert"]:not(#__next-route-announcer__)');

test.describe("hero workspace", () => {
  test("renders the headline, workspace and trust signals", async ({ page }) => {
    await page.goto("/");
    const hero = page.locator("section[aria-labelledby='hero-heading']");
    await expect(hero.getByRole("heading", { level: 1 })).toContainText("Paste anything.");
    await expect(hero.getByRole("button", { name: "Analyze" })).toBeEnabled();
    await expect(hero.getByText("No account · Files auto-delete")).toBeVisible();
    await expect(hero.getByRole("button", { name: /choose file/i })).toBeVisible();
  });

  test("URL input shows the detected host without claiming capabilities", async ({ page }) => {
    await page.goto("/");
    const input = page.getByLabel("Paste a URL or upload a file");
    await input.fill("https://www.example.com/talk.mp4");
    const hint = page.getByText("example.com", { exact: true });
    await expect(hint).toBeVisible();
    await expect(page.getByText("Press Analyze to see what this source allows.")).toBeVisible();
  });

  test("submitting a URL shows an honest analyzing state, then the server's answer", async ({
    page,
  }) => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => (release = resolve));
    await page.route("**/api/v1/analyze", async (route) => {
      await gate;
      await route.fulfill({
        status: 400,
        json: {
          error: {
            code: "UNSUPPORTED_SCHEME",
            message: "Only http and https URLs are supported.",
            retryable: false,
          },
        },
      });
    });
    await page.goto(`/analyze?url=${encodeURIComponent("https://example.com/a.mp4")}`);
    // Loading: a single real stage with no invented percentage.
    await expect(page.getByText(/Analyzing/).first()).toBeVisible();
    await expect(page.locator('[role="progressbar"][aria-valuenow]')).toHaveCount(0);
    release();
    // Error: icon + title + the server's exact message + next step.
    const panel = alerts(page).first();
    await expect(panel).toContainText("We can't open this kind of link.");
    await expect(panel).toContainText("Only http and https URLs are supported.");
    await expect(panel).toContainText("Use a regular http or https address.");
  });

  test("rate limits count down from the server's Retry-After before retry unlocks", async ({
    page,
  }) => {
    await page.route("**/api/v1/analyze", (route) =>
      route.fulfill({
        status: 429,
        headers: { "Retry-After": "3", "Access-Control-Expose-Headers": "Retry-After" },
        json: {
          error: { code: "RATE_LIMITED", message: "Too many requests.", retryable: true },
        },
      }),
    );
    await page.goto(`/analyze?url=${encodeURIComponent("https://example.com/a.mp4")}`);
    const retry = page.getByRole("button", { name: /try again/i });
    await expect(retry).toBeDisabled();
    await expect(retry).toHaveText(/in \d+s/);
    await expect(retry).toBeEnabled({ timeout: 6_000 });
  });

  test("files over the limit shake the drop zone and are refused locally", async ({ page }) => {
    await page.route("**/api/v1/limits", (route) =>
      route.fulfill({
        json: {
          max_upload_bytes: 1024,
          max_file_bytes: 1024,
          max_url_length: 2048,
          max_text_chars: 10000,
          max_files_per_job: 50,
          result_ttl_seconds: 1800,
          upload_ttl_seconds: 1800,
        },
      }),
    );
    await page.goto("/tools/image-compressor");
    await page.locator('input[type="file"]').setInputFiles({
      name: "big.png",
      mimeType: "image/png",
      buffer: Buffer.alloc(4096),
    });
    await expect(page.getByRole("list", { name: "Selected file" })).toContainText("big.png");
    await page.getByRole("button", { name: "Analyze" }).click();
    await expect(alerts(page).first()).toContainText("This file is too large.");
    await expect(page.locator(".animate-shake").first()).toBeAttached();
  });
});

test.describe("platform refusals", () => {
  test("a YouTube refusal explains why and offers honest alternatives", async ({ page }) => {
    await page.route("**/api/v1/analyze", (route) =>
      route.fulfill({
        json: {
          normalized_url: "https://youtu.be/example",
          source_kind: "platform",
          resource_type: "UNKNOWN",
          platform: "youtube",
          capabilities: [],
          tools: [],
          formats: [],
          restrictions: ["public_content_only"],
          warnings: [],
          resource_counts: {},
          status: "unsupported",
          reason: {
            code: "SOURCE_UNREACHABLE",
            message: "The platform is temporarily limiting requests from this server.",
            retryable: true,
          },
        },
      }),
    );
    await page.goto(`/analyze?url=${encodeURIComponent("https://youtu.be/example")}`);
    await expect(
      page.getByRole("heading", { name: "Why YouTube links often fail here" }),
    ).toBeVisible();
    await expect(page.getByText(/Direct video links and file uploads always work/)).toBeVisible();
    const selfHost = page.getByRole("link", { name: /How to run it yourself/ });
    await expect(selfHost).toHaveAttribute("href", /#run-it-on-your-own-computer$/);
    await expect(selfHost).toHaveAttribute("rel", /noopener/);
    // Never a download button for a refused source.
    await expect(page.getByRole("link", { name: "Download", exact: true })).toHaveCount(0);
  });

  test("other platform refusals do not show the YouTube note", async ({ page }) => {
    await page.route("**/api/v1/analyze", (route) =>
      route.fulfill({
        json: {
          normalized_url: "https://vimeo.com/1",
          source_kind: "platform",
          resource_type: "UNKNOWN",
          platform: "vimeo",
          capabilities: [],
          tools: [],
          formats: [],
          restrictions: [],
          warnings: [],
          resource_counts: {},
          status: "restricted",
          reason: { code: "SOURCE_PRIVATE", message: "This video is private.", retryable: false },
        },
      }),
    );
    await page.goto(`/analyze?url=${encodeURIComponent("https://vimeo.com/1")}`);
    await expect(page.getByText("This video is private.")).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Why YouTube links often fail here" }),
    ).toHaveCount(0);
  });

  test("video tool pages mention the YouTube limitation", async ({ page }) => {
    await page.goto("/tools/video-downloader");
    await expect(page.getByText(/YouTube currently blocks many servers/)).toBeVisible();
    await page.goto("/tools/image-compressor");
    await expect(page.getByText(/YouTube currently blocks many servers/)).toHaveCount(0);
  });
});

test.describe("tool discovery", () => {
  test("search filters instantly and shows an empty state", async ({ page }) => {
    await page.goto("/tools");
    const results = page.locator("#catalogue-results [data-tool-card]");
    const total = await results.count();
    expect(total).toBeGreaterThan(20);
    await page.getByLabel("Search tools").fill("merge");
    await expect(results).toHaveCount(1);
    await expect(results.first()).toContainText("PDF merger");
    await page.getByLabel("Search tools").fill("zzzz-not-a-tool");
    await expect(page.getByRole("heading", { name: /No tools match/ })).toBeVisible();
    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(results).toHaveCount(total);
  });

  test("category tabs filter, support arrow keys, and deep-link by hash", async ({ page }) => {
    await page.goto("/tools#pdf");
    const pdfTab = page.getByRole("tab", { name: /PDF/ });
    await expect(pdfTab).toHaveAttribute("aria-selected", "true");
    const results = page.locator("#catalogue-results [data-tool-card]");
    await expect(results.first()).toContainText(/PDF/);
    await pdfTab.focus();
    await page.keyboard.press("ArrowRight");
    const webTab = page.getByRole("tab", { name: /^Web/ });
    await expect(webTab).toHaveAttribute("aria-selected", "true");
    await expect(webTab).toBeFocused();
    await page.keyboard.press("Home");
    await expect(page.getByRole("tab", { name: /^All/ })).toHaveAttribute("aria-selected", "true");
  });

  test("/ focuses the tool search", async ({ page }) => {
    await page.goto("/tools");
    await page.locator("body").click({ position: { x: 5, y: 300 } });
    await page.keyboard.press("/");
    await expect(page.getByLabel("Search tools")).toBeFocused();
  });
});

test.describe("themes, mobile and motion", () => {
  test("dark mode applies the dark surface tokens", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "dark" });
    await page.goto("/");
    await expect(page.locator("html")).toHaveClass(/dark/);
    const background = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(background).toBe("rgb(5, 11, 25)");
  });

  test("mobile menu opens, lists navigation, and closes with Escape", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    await page.getByRole("button", { name: "Open menu" }).click();
    const nav = page.getByRole("navigation", { name: "Mobile" });
    await expect(nav.getByRole("link", { name: "Tools" })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(nav).toHaveCount(0);
  });

  for (const width of [375, 768, 1024, 1440, 1920]) {
    test(`no horizontal overflow on key pages at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      for (const path of ["/", "/tools", "/tools/video-to-mp3", "/extension"]) {
        await page.goto(path);
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(overflow, `${path} at ${width}px`).toBeLessThanOrEqual(1);
      }
    });
  }

  test("reduced motion shows all content and stops decorative loops", async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.goto("/");
    // Scroll-reveal content is visible without scrolling.
    const tile = page.locator(".reveal").last();
    await expect(tile).toHaveCSS("opacity", "1");
    const drift = page.locator(".animate-drift").first();
    await expect(drift).toHaveCSS("animation-name", "none");
    // The demo does not auto-advance and offers no play control.
    await expect(page.getByRole("button", { name: /pause demo/i })).toHaveCount(0);
  });

  test("visitors can pause decorative animation from the footer", async ({ page }) => {
    await page.goto("/");
    const toggle = page.getByRole("button", { name: "Pause animations" });
    await toggle.click();
    await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
    await expect(page.locator(".animate-aurora").first()).toHaveCSS(
      "animation-play-state",
      "paused",
    );
    await expect(page.getByRole("button", { name: "Resume animations" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });
});

test.describe("processing and success (API)", () => {
  test.skip(!process.env.E2E_API, "Requires a local API (set E2E_API=1 in CI)");

  test("upload shows real stages and a rewarding result surface", async ({ page }) => {
    test.setTimeout(120_000);
    const png = Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
      "base64",
    );
    await page.goto("/tools/image-to-webp");
    await page
      .locator('input[type="file"]')
      .setInputFiles({ name: "pixel.png", mimeType: "image/png", buffer: png });
    await page.getByRole("button", { name: "Analyze" }).click();
    const journey = page.getByRole("complementary", { name: "Progress and details" });
    await expect(journey.getByText("Analyze: Done")).toBeAttached({ timeout: 20_000 });
    await expect(journey.getByText("Choose a tool: Your turn")).toBeAttached();
    await page.getByRole("button", { name: "Start" }).click();
    await expect(page.getByRole("heading", { name: /your result/i })).toBeVisible({
      timeout: 60_000,
    });
    const surface = page.getByRole("region", { name: /\.webp$/i });
    await expect(surface.getByText("Ready", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Process another" })).toHaveAttribute(
      "href",
      "/tools/image-to-webp",
    );
    await expect(page.getByText(/automatically deleted in/)).toBeVisible();
  });
});
