// @ts-check
/**
 * Service worker: owns the context menu. It never reads page content, never injects
 * scripts and keeps no history. A menu click hands the clicked page's URL to the popup
 * (session storage, cleared when the browser closes); if the popup cannot be opened
 * programmatically, the same request opens on the website instead.
 */

import { DEFAULT_SERVER_ORIGIN, PENDING_ACTION_KEY, SERVER_ORIGIN_KEY } from "./config.js";
import { FINDERS, analyzablePageUrl, siteLink } from "./capabilities.js";

const ROOT_MENU = "anything-download";
const MENU_ITEMS = [
  { id: "analyze", title: "Analyze this page" },
  { id: "images", title: FINDERS.images.label },
  { id: "videos", title: FINDERS.videos.label },
  { id: "audio", title: FINDERS.audio.label },
  { id: "pdfs", title: FINDERS.pdfs.label },
  { id: "open", title: "Open in Anything Download" },
];

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    // Only offered on normal web pages; browser-internal pages are never analyzed.
    const documentUrlPatterns = ["http://*/*", "https://*/*"];
    chrome.contextMenus.create({ id: ROOT_MENU, title: "Anything Download", contexts: ["page"], documentUrlPatterns });
    for (const item of MENU_ITEMS) {
      chrome.contextMenus.create({
        id: `${ROOT_MENU}:${item.id}`,
        parentId: ROOT_MENU,
        title: item.title,
        contexts: ["page"],
        documentUrlPatterns,
      });
    }
  });
});

chrome.contextMenus.onClicked.addListener((info) => {
  void handleMenuClick(String(info.menuItemId), info.pageUrl);
});

/**
 * @param {string} menuItemId
 * @param {string | undefined} rawPageUrl
 */
export async function handleMenuClick(menuItemId, rawPageUrl) {
  const action = menuItemId.startsWith(`${ROOT_MENU}:`) ? menuItemId.slice(ROOT_MENU.length + 1) : null;
  const pageUrl = analyzablePageUrl(rawPageUrl);
  if (!action || !pageUrl) {
    return;
  }
  const origin = await serverOrigin();

  if (action === "open") {
    await chrome.tabs.create({ url: siteLink(origin, pageUrl) });
    return;
  }

  const focus = action === "analyze" ? null : action;
  await chrome.storage.session.set({ [PENDING_ACTION_KEY]: { pageUrl, focus, createdAt: Date.now() } });
  try {
    await chrome.action.openPopup();
  } catch {
    // openPopup can be refused (e.g. no focused window); continue on the website.
    await chrome.storage.session.remove(PENDING_ACTION_KEY);
    const tool = focus ? FINDERS[/** @type {keyof typeof FINDERS} */ (focus)].tool : null;
    await chrome.tabs.create({ url: siteLink(origin, pageUrl, tool) });
  }
}

// Chrome offers no API to click a context-menu item, so tests call the handler
// directly through the service worker's own global. Web pages cannot reach it.
/** @type {any} */ (globalThis).handleMenuClick = handleMenuClick;

async function serverOrigin() {
  const stored = await chrome.storage.local.get(SERVER_ORIGIN_KEY);
  return typeof stored[SERVER_ORIGIN_KEY] === "string" ? stored[SERVER_ORIGIN_KEY] : DEFAULT_SERVER_ORIGIN;
}
