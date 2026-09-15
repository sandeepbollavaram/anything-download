import { expect, test } from "@playwright/test";

/**
 * Isolated on purpose. Rate limits are keyed by client IP + route bucket, and
 * this test deliberately exhausts the /analyze bucket. Every E2E test shares one
 * source IP, so running it alongside the other analyze-backed specs starves them
 * and they fail with 429 instead of the assertion they care about.
 *
 * Keep this file in its own Playwright shard/job, or run it with --workers=1
 * after the rest, so the flood cannot overlap them.
 */
test.describe.configure({ mode: "serial" });

test.describe("rate limiting", () => {
  test.skip(!process.env.E2E_API, "Requires a local API (set E2E_API=1 in CI)");

  test("analyze rate limit returns 429 with Retry-After", async ({ request }) => {
    let saw429 = false;
    for (let i = 0; i < 60; i += 1) {
      const response = await request.post("/api/v1/analyze", {
        data: { url: `javascript:probe-${i}` },
      });
      if (response.status() === 429) {
        saw429 = true;
        expect(response.headers()["retry-after"]).toBeTruthy();
        const body = (await response.json()) as { error?: { code?: string } };
        expect(body.error?.code).toBe("RATE_LIMITED");
        break;
      }
    }
    expect(saw429, "expected the analyze bucket to start rejecting").toBeTruthy();
  });
});
