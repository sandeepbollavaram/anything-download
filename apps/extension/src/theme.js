// @ts-check
export const THEME_KEY = "theme";

/** Applies the saved theme ("system" follows the operating system). */
export async function applyStoredTheme() {
  const stored = await chrome.storage.local.get(THEME_KEY);
  applyTheme(stored[THEME_KEY]);
}

/** @param {unknown} theme */
export function applyTheme(theme) {
  if (theme === "light" || theme === "dark") {
    document.documentElement.dataset.theme = theme;
  } else {
    delete document.documentElement.dataset.theme;
  }
}
