// @ts-check
/**
 * Turns an API analysis or failure into what the popup shows. Pure functions only.
 *
 * Rule: an action that leads to processing is only offered when the server listed the
 * matching tool for this URL. Restricted or unsupported sources get an explanation and,
 * at most, a link to read more on the website, never a download action.
 */

/** Finder tools the popup and context menu can open, keyed by the menu action id. */
export const FINDERS = /** @type {const} */ ({
  images: { tool: "website-image-gallery", label: "Find images", counts: ["IMAGE"] },
  videos: { tool: "website-video-finder", label: "Find videos", counts: ["VIDEO"] },
  audio: { tool: "website-audio-finder", label: "Find audio", counts: ["AUDIO"] },
  pdfs: { tool: "website-pdf-finder", label: "Find PDFs", counts: ["PDF", "DOCUMENT"] },
});

/** Restriction reasons the server reports, with a short, honest label. */
const RESTRICTED_LABELS = /** @type {Record<string, string>} */ ({
  SOURCE_REQUIRES_AUTH: "Login required",
  SOURCE_PRIVATE: "Private content",
  SOURCE_DRM_PROTECTED: "DRM protected",
  SOURCE_GEO_RESTRICTED: "Not available in this region",
  SOURCE_LIVE_STREAM: "Live stream",
  SOURCE_FORBIDDEN: "Access denied by the source",
});

const REJECTED_LABELS = /** @type {Record<string, string>} */ ({
  BLOCKED_TARGET: "Private or local address",
  UNSUPPORTED_SCHEME: "Unsupported address",
  INVALID_URL: "Not a valid web address",
  URL_TOO_LONG: "Address too long",
});

const TYPE_LABELS = /** @type {Record<string, string>} */ ({
  VIDEO: "Video",
  IMAGE: "Image",
  AUDIO: "Audio",
  PDF: "PDF",
  DOCUMENT: "Document",
  WEBPAGE: "Web page",
  ARCHIVE: "Archive",
  UNKNOWN: "File",
});

/**
 * @typedef {{ id: string, label: string, tool: string | null, count: number | null }} Action
 * @typedef {{
 *   tone: "success" | "warning" | "info" | "error",
 *   heading: string,
 *   message: string,
 *   detail: string | null,
 *   actions: Action[],
 *   retryAfterSeconds: number | null,
 *   retryable: boolean,
 *   openSite: boolean,
 * }} View
 */

/**
 * @param {any} analysis a URLAnalysis already validated by api.js
 * @param {keyof typeof FINDERS | null} [focus] finder requested from the context menu
 * @returns {View}
 */
export function describeAnalysis(analysis, focus = null) {
  if (analysis.status === "restricted") {
    return {
      tone: "warning",
      heading: RESTRICTED_LABELS[analysis.reason.code] ?? "Restricted content",
      message: analysis.reason.message,
      detail: "Anything Download only works with content you can access publicly.",
      actions: [],
      retryAfterSeconds: null,
      retryable: false,
      openSite: false,
    };
  }
  if (analysis.status === "unsupported") {
    return {
      tone: "info",
      heading: "Not supported",
      message: analysis.reason.message,
      detail: null,
      actions: [],
      retryAfterSeconds: null,
      retryable: false,
      openSite: false,
    };
  }

  const tools = new Set(analysis.tools);
  const counts = analysis.resource_counts ?? {};
  /** @type {Action[]} */
  const actions = [];
  for (const [id, finder] of Object.entries(FINDERS)) {
    if (!tools.has(finder.tool)) {
      continue; // the server did not offer it for this page
    }
    const count = finder.counts.reduce((sum, key) => sum + (counts[key] ?? 0), 0);
    if (count === 0) {
      continue; // nothing of that kind was found; do not offer an empty search
    }
    actions.push({ id, label: finder.label, tool: finder.tool, count });
  }
  if (focus) {
    actions.sort((a, b) => Number(b.id === focus) - Number(a.id === focus));
  }

  const kind = TYPE_LABELS[analysis.resource_type] ?? "Resource";
  const heading = analysis.title ? String(analysis.title) : kind;
  let message;
  if (analysis.source_kind === "webpage") {
    const found = actions.map((a) => `${a.count} ${a.label.replace("Find ", "")}`);
    message = found.length ? `Found ${found.join(", ")}.` : "No public media was found on this page.";
  } else if (analysis.source_kind === "platform") {
    message = `${kind} from ${analysis.platform ?? "a supported platform"}.`;
  } else {
    message = `${kind} file.`;
  }

  const focusMissing = focus && !actions.some((a) => a.id === focus);
  return {
    tone: tools.size > 0 ? "success" : "info",
    heading,
    message,
    detail: focusMissing ? `No ${FINDERS[focus].label.replace("Find ", "")} were found here.` : null,
    actions,
    retryAfterSeconds: null,
    retryable: false,
    openSite: tools.size > 0,
  };
}

/**
 * @param {import("./api.js").ApiFailure | Error} failure
 * @returns {View}
 */
export function describeFailure(failure) {
  const f = /** @type {any} */ (failure);
  const base = { detail: null, actions: [], retryAfterSeconds: null, openSite: false };
  switch (f.kind) {
    case "rejected":
      return {
        ...base,
        tone: "warning",
        heading: REJECTED_LABELS[f.code] ?? "This address can't be processed",
        message: f.message,
        retryable: false,
      };
    case "rate_limited":
      return {
        ...base,
        tone: "warning",
        heading: "Too many requests",
        message: f.message,
        retryAfterSeconds: f.retryAfterSeconds,
        retryable: true,
      };
    case "unavailable":
      return { ...base, tone: "error", heading: "Service unavailable", message: f.message, retryable: true };
    case "timeout":
    case "network":
      return { ...base, tone: "error", heading: "Can't reach Anything Download", message: f.message, retryable: true };
    case "permission":
      return {
        ...base,
        tone: "error",
        heading: "Permission needed",
        message: f.message,
        detail: "Open the extension options to allow access to your server.",
        retryable: false,
      };
    case "malformed":
      return { ...base, tone: "error", heading: "Unexpected response", message: f.message, retryable: true };
    default:
      return { ...base, tone: "error", heading: "Something went wrong", message: "Please try again.", retryable: true };
  }
}

/**
 * Only http(s) pages can be analyzed. Browser-internal pages are refused locally so their
 * address is never sent anywhere; everything else is judged by the server.
 * @param {string | undefined | null} url
 */
export function analyzablePageUrl(url) {
  if (!url) {
    return null;
  }
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

/**
 * Website deep link that continues the work in the browser tab.
 * @param {string} serverOrigin
 * @param {string} pageUrl
 * @param {string | null} [tool]
 */
export function siteLink(serverOrigin, pageUrl, tool = null) {
  const params = new URLSearchParams({ url: pageUrl });
  if (tool) {
    params.set("tool", tool);
  }
  return `${serverOrigin}/analyze?${params.toString()}`;
}
