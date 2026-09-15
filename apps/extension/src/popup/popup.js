// @ts-check
import { ApiFailure, analyzeUrl } from "../api.js";
import { analyzablePageUrl, describeAnalysis, describeFailure, siteLink } from "../capabilities.js";
import {
  DEFAULT_SERVER_ORIGIN,
  PENDING_ACTION_KEY,
  PENDING_ACTION_MAX_AGE_MS,
  SERVER_ORIGIN_KEY,
} from "../config.js";
import { applyStoredTheme } from "../theme.js";

const ICON_FOR_TONE = { success: "#i-check", warning: "#i-alert", info: "#i-info", error: "#i-error" };
const ICON_FOR_ACTION = { images: "#i-image", videos: "#i-video", audio: "#i-audio", pdfs: "#i-pdf" };

const el = {
  host: /** @type {HTMLElement} */ (document.getElementById("page-host")),
  url: /** @type {HTMLElement} */ (document.getElementById("page-url")),
  analyze: /** @type {HTMLButtonElement} */ (document.getElementById("analyze")),
  openSite: /** @type {HTMLButtonElement} */ (document.getElementById("open-site")),
  settings: /** @type {HTMLButtonElement} */ (document.getElementById("settings")),
  result: /** @type {HTMLElement} */ (document.getElementById("result")),
  skeleton: /** @type {HTMLElement} */ (document.getElementById("skeleton")),
  panel: /** @type {HTMLElement} */ (document.getElementById("panel")),
  toneIcon: /** @type {SVGUseElement} */ (document.querySelector("#tone-icon use")),
  heading: /** @type {HTMLElement} */ (document.getElementById("heading")),
  message: /** @type {HTMLElement} */ (document.getElementById("message")),
  detail: /** @type {HTMLElement} */ (document.getElementById("detail")),
  actions: /** @type {HTMLElement} */ (document.getElementById("actions")),
  retry: /** @type {HTMLButtonElement} */ (document.getElementById("retry")),
};

/** @type {{ origin: string, pageUrl: string | null, focus: any, countdown: number | undefined }} */
const state = { origin: DEFAULT_SERVER_ORIGIN, pageUrl: null, focus: null, countdown: undefined };

async function init() {
  await applyStoredTheme();
  const stored = await chrome.storage.local.get(SERVER_ORIGIN_KEY);
  if (typeof stored[SERVER_ORIGIN_KEY] === "string") {
    state.origin = stored[SERVER_ORIGIN_KEY];
  }

  el.settings.addEventListener("click", () => void chrome.runtime.openOptionsPage());
  el.analyze.addEventListener("click", () => void runAnalysis());
  el.retry.addEventListener("click", () => void runAnalysis());
  el.openSite.addEventListener("click", () => {
    if (state.pageUrl) {
      void openTab(siteLink(state.origin, state.pageUrl));
    }
  });

  const pending = await takePendingAction();
  const pageUrl = pending?.pageUrl ?? (await activeTabUrl());
  showPage(pageUrl);
  if (pending && state.pageUrl) {
    state.focus = pending.focus ?? null;
    await runAnalysis(); // the user already chose this action from the context menu
  }
}

/**
 * A request left by the context menu, if it is recent. Consumed once.
 * @returns {Promise<{ pageUrl: string, focus: string | null, createdAt: number } | null>}
 */
async function takePendingAction() {
  const stored = await chrome.storage.session.get(PENDING_ACTION_KEY);
  /** @type {any} */
  const pending = stored[PENDING_ACTION_KEY];
  if (!pending) {
    return null;
  }
  await chrome.storage.session.remove(PENDING_ACTION_KEY);
  if (typeof pending.createdAt !== "number" || Date.now() - pending.createdAt > PENDING_ACTION_MAX_AGE_MS) {
    return null;
  }
  return pending;
}

/**
 * The address of the tab the user opened the popup on. With only `activeTab`, the URL is
 * visible for that tab alone and only because the user clicked the extension.
 */
async function activeTabUrl() {
  const requested = Number.parseInt(new URLSearchParams(location.search).get("tabId") ?? "", 10);
  if (Number.isInteger(requested)) {
    const tab = await chrome.tabs.get(requested).catch(() => null);
    return tab?.url ?? null;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab?.url ?? null;
}

/** @param {string | null} rawUrl */
function showPage(rawUrl) {
  const pageUrl = analyzablePageUrl(rawUrl);
  state.pageUrl = pageUrl;
  if (!pageUrl) {
    el.host.textContent = "This page can't be analyzed";
    el.url.textContent = "Open a regular web page (http or https) and try again.";
    el.analyze.disabled = true;
    el.openSite.disabled = true;
    return;
  }
  const parsed = new URL(pageUrl);
  el.host.textContent = parsed.hostname;
  el.url.textContent = pageUrl;
  el.url.title = pageUrl;
  el.analyze.disabled = false;
  el.openSite.disabled = false;
}

async function runAnalysis() {
  if (!state.pageUrl) {
    return;
  }
  stopCountdown();
  setLoading(true);
  try {
    if (!(await hasServerPermission())) {
      throw new ApiFailure("permission", `The extension is not allowed to contact ${state.origin}.`);
    }
    const analysis = await analyzeUrl(state.origin, state.pageUrl);
    render(describeAnalysis(analysis, state.focus));
  } catch (error) {
    render(describeFailure(error instanceof Error ? error : new Error(String(error))));
  } finally {
    setLoading(false);
  }
}

async function hasServerPermission() {
  try {
    return await chrome.permissions.contains({ origins: [`${state.origin}/*`] });
  } catch {
    return false;
  }
}

/** @param {boolean} loading */
function setLoading(loading) {
  el.analyze.disabled = loading || !state.pageUrl;
  el.analyze.classList.toggle("is-loading", loading);
  /** @type {HTMLElement} */ (el.analyze.querySelector(".label")).textContent = loading
    ? "Analyzing…"
    : "Analyze this page";
  el.result.hidden = false;
  el.result.setAttribute("aria-busy", String(loading));
  el.skeleton.hidden = !loading;
  if (loading) {
    el.panel.hidden = true;
    el.result.removeAttribute("data-tone");
  }
}

/** @param {import("../capabilities.js").View} view */
function render(view) {
  // Role first, then content, so assistive technology announces the new text.
  el.panel.setAttribute("role", view.tone === "error" || view.tone === "warning" ? "alert" : "status");
  el.panel.hidden = false;
  el.result.dataset.tone = view.tone;
  el.toneIcon.setAttribute("href", ICON_FOR_TONE[view.tone]);
  // Server-provided text is only ever assigned as text, never parsed as HTML.
  el.heading.textContent = view.heading;
  el.message.textContent = view.message;
  el.detail.hidden = !view.detail;
  el.detail.textContent = view.detail ?? "";

  el.actions.replaceChildren(
    ...view.actions.map((action) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "action";
      button.append(icon(ICON_FOR_ACTION[/** @type {keyof typeof ICON_FOR_ACTION} */ (action.id)] ?? "#i-info"));
      const label = document.createElement("span");
      label.textContent = action.label;
      button.append(label);
      if (action.count !== null) {
        const count = document.createElement("span");
        count.className = "count";
        count.textContent = String(action.count);
        button.append(count);
        button.setAttribute("aria-label", `${action.label}: ${action.count} found. Opens in Anything Download.`);
      }
      button.addEventListener("click", () => {
        if (state.pageUrl) {
          void openTab(siteLink(state.origin, state.pageUrl, action.tool));
        }
      });
      item.append(button);
      return item;
    }),
  );

  el.openSite.classList.toggle("emphasis", view.openSite);
  el.retry.hidden = !view.retryable;
  if (view.retryAfterSeconds) {
    startCountdown(view.retryAfterSeconds);
  } else {
    el.retry.disabled = false;
    el.retry.textContent = "Try again";
  }
}

/** @param {number} seconds */
function startCountdown(seconds) {
  let remaining = seconds;
  const tick = () => {
    if (remaining <= 0) {
      stopCountdown();
      return;
    }
    el.retry.disabled = true;
    el.retry.textContent = `Try again in ${remaining} s`;
    remaining -= 1;
  };
  tick();
  state.countdown = window.setInterval(tick, 1000);
}

function stopCountdown() {
  if (state.countdown !== undefined) {
    window.clearInterval(state.countdown);
    state.countdown = undefined;
  }
  el.retry.disabled = false;
  el.retry.textContent = "Try again";
}

/** @param {string} href */
function icon(href) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS(ns, "use");
  use.setAttribute("href", href);
  svg.append(use);
  return svg;
}

/** @param {string} url */
async function openTab(url) {
  await chrome.tabs.create({ url });
  window.close();
}

void init();
