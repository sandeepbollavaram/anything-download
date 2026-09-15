import { expect, test } from "@playwright/test";

const pages = [
  { path: "/about", heading: "About" },
  { path: "/extension", heading: "Chrome extension" },
  { path: "/privacy", heading: "Privacy" },
  { path: "/terms", heading: "Terms" },
  { path: "/copyright", heading: "Copyright" },
  { path: "/security", heading: "Security" },
  { path: "/contact", heading: "Contact" },
];

for (const item of pages) {
  test(`${item.path} renders`, async ({ page }) => {
    await page.goto(item.path);
    await expect(page.getByRole("heading", { name: item.heading, level: 1 })).toBeVisible();
  });
}
