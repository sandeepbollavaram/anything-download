// @ts-check
/**
 * Where the extension sends work. The public service serves the website and the API
 * on one origin (the reverse proxy routes /api/* to FastAPI), so one origin is enough.
 * A self-hosted server can be chosen on the options page; the extension then asks
 * for host permission for that single origin only.
 */

export const DEFAULT_SERVER_ORIGIN = "https://anythingdownload.in";
export const SERVER_ORIGIN_KEY = "serverOrigin";

/** Context-menu requests are handed to the popup through session storage. */
export const PENDING_ACTION_KEY = "pendingAction";
/** A pending request older than this is ignored (the user moved on). */
export const PENDING_ACTION_MAX_AGE_MS = 60_000;

export const REQUEST_TIMEOUT_MS = 20_000;

/**
 * Validates a server origin typed by the user. HTTPS is required, except for a local
 * development server. This is a usability check only; the server enforces everything.
 * @param {string} value
 * @returns {string | null} the normalized origin, or null when unacceptable
 */
export function normalizeServerOrigin(value) {
  let url;
  try {
    url = new URL(value.trim());
  } catch {
    return null;
  }
  if (url.username || url.password) {
    return null;
  }
  const local = url.hostname === "localhost" || url.hostname === "127.0.0.1";
  if (url.protocol !== "https:" && !(url.protocol === "http:" && local)) {
    return null;
  }
  return url.origin;
}
