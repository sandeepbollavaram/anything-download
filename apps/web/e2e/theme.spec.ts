import { expect, test } from "@playwright/test";

test("theme toggle switches to dark mode", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /color theme|switch color theme|theme/i }).click();
  await page.getByRole("menuitemradio", { name: "Dark" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);

  // Reopen: the chosen theme must be exposed as the checked radio, and only it.
  await page.getByRole("button", { name: /color theme|switch color theme|theme/i }).click();
  await expect(page.getByRole("menuitemradio", { name: "Dark" })).toHaveAttribute("aria-checked", "true");
  await expect(page.getByRole("menuitemradio", { name: "Light" })).toHaveAttribute("aria-checked", "false");
  await expect(page.getByRole("menuitem")).toHaveCount(0);
});

test("theme toggle is keyboard reachable", async ({ page }) => {
  await page.goto("/");
  const toggle = page.getByRole("button", { name: /color theme|switch color theme|theme/i });
  await toggle.focus();
  await expect(toggle).toBeFocused();
});
