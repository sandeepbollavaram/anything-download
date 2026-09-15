// @ts-check
import { DEFAULT_SERVER_ORIGIN, SERVER_ORIGIN_KEY, normalizeServerOrigin } from "../config.js";
import { THEME_KEY, applyStoredTheme, applyTheme } from "../theme.js";

const form = /** @type {HTMLFormElement} */ (document.getElementById("server-form"));
const input = /** @type {HTMLInputElement} */ (document.getElementById("server"));
const error = /** @type {HTMLElement} */ (document.getElementById("server-error"));
const status = /** @type {HTMLElement} */ (document.getElementById("server-status"));
const reset = /** @type {HTMLButtonElement} */ (document.getElementById("reset"));
const theme = /** @type {HTMLSelectElement} */ (document.getElementById("theme"));

async function init() {
  await applyStoredTheme();
  const stored = await chrome.storage.local.get([SERVER_ORIGIN_KEY, THEME_KEY]);
  input.value = typeof stored[SERVER_ORIGIN_KEY] === "string" ? stored[SERVER_ORIGIN_KEY] : DEFAULT_SERVER_ORIGIN;
  theme.value = typeof stored[THEME_KEY] === "string" ? stored[THEME_KEY] : "system";

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void saveServer(input.value);
  });
  reset.addEventListener("click", () => {
    input.value = DEFAULT_SERVER_ORIGIN;
    void saveServer(DEFAULT_SERVER_ORIGIN);
  });
  theme.addEventListener("change", () => {
    applyTheme(theme.value);
    void chrome.storage.local.set({ [THEME_KEY]: theme.value });
  });
}

/** @param {string} value */
async function saveServer(value) {
  const origin = normalizeServerOrigin(value);
  if (!origin) {
    showError("Enter an address starting with https:// (or http://localhost for development).");
    return;
  }
  showError(null);
  if (origin !== DEFAULT_SERVER_ORIGIN) {
    // Host access is granted for this single origin, at the user's request.
    const granted = await chrome.permissions.request({ origins: [`${origin}/*`] }).catch(() => false);
    if (!granted) {
      showError(`Access to ${origin} was not allowed, so the setting was not changed.`);
      return;
    }
  }
  const previous = (await chrome.storage.local.get(SERVER_ORIGIN_KEY))[SERVER_ORIGIN_KEY];
  await chrome.storage.local.set({ [SERVER_ORIGIN_KEY]: origin });
  if (typeof previous === "string" && previous !== origin && previous !== DEFAULT_SERVER_ORIGIN) {
    await chrome.permissions.remove({ origins: [`${previous}/*`] }).catch(() => false);
  }
  input.value = origin;
  status.textContent = `Saved. The extension now uses ${origin}.`;
}

/** @param {string | null} message */
function showError(message) {
  error.hidden = !message;
  error.textContent = message ?? "";
  input.setAttribute("aria-invalid", String(Boolean(message)));
  if (message) {
    status.textContent = "";
    input.focus();
  }
}

void init();
