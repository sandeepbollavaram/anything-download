import { defineConfig } from "@playwright/test";

// Each test launches its own Chromium with the unpacked extension loaded, so tests run
// one at a time. Extensions need the full Chromium build ("chromium" channel), not the
// headless shell.
export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: /.*\.spec\.mjs$/,
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  timeout: 60_000,
});
