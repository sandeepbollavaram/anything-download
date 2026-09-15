// @ts-check
/**
 * Client for the existing public Anything Download API. The extension adds no API of
 * its own: it calls the same endpoints as the website, and the server stays
 * authoritative for URL validation, SSRF protection, rate limits and every other
 * control. Nothing here decides what is allowed; it only reports what the server said.
 */

import { REQUEST_TIMEOUT_MS } from "./config.js";

/**
 * @typedef {"network" | "timeout" | "rate_limited" | "unavailable" | "rejected" | "malformed" | "permission"} FailureKind
 */

export class ApiFailure extends Error {
  /**
   * @param {FailureKind} kind
   * @param {string} message
   * @param {{ code?: string, status?: number, retryAfterSeconds?: number | null }} [extra]
   */
  constructor(kind, message, extra = {}) {
    super(message);
    this.name = "ApiFailure";
    this.kind = kind;
    this.code = extra.code ?? null;
    this.status = extra.status ?? null;
    this.retryAfterSeconds = extra.retryAfterSeconds ?? null;
  }
}

const ANALYSIS_STATUSES = new Set(["ok", "unsupported", "restricted"]);
const SOURCE_KINDS = new Set(["direct", "webpage", "platform"]);

/**
 * POST /api/v1/analyze for one URL the user explicitly asked about.
 * @param {string} serverOrigin
 * @param {string} pageUrl
 * @param {{ fetchImpl?: typeof fetch, timeoutMs?: number }} [options]
 * @returns {Promise<object>} a validated URLAnalysis
 */
export async function analyzeUrl(serverOrigin, pageUrl, options = {}) {
  const body = await request(`${serverOrigin}/api/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: pageUrl }),
    ...options,
  });
  return validateAnalysis(body);
}

/**
 * @param {string} url
 * @param {{ method: string, headers: Record<string, string>, body: string, fetchImpl?: typeof fetch, timeoutMs?: number }} init
 */
async function request(url, init) {
  const fetchImpl = init.fetchImpl ?? fetch;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), init.timeoutMs ?? REQUEST_TIMEOUT_MS);
  let response;
  try {
    response = await fetchImpl(url, {
      method: init.method,
      headers: init.headers,
      body: init.body,
      signal: controller.signal,
      // The extension never sends or receives cookies or other credentials.
      credentials: "omit",
      cache: "no-store",
      redirect: "error",
    });
  } catch (error) {
    if (controller.signal.aborted) {
      throw new ApiFailure("timeout", "The server took too long to respond.");
    }
    throw new ApiFailure("network", "The server could not be reached. Check your connection.");
  } finally {
    clearTimeout(timer);
  }

  const payload = await readJson(response);
  if (response.ok) {
    if (payload === undefined) {
      throw new ApiFailure("malformed", "The server returned a response the extension could not read.");
    }
    return payload;
  }
  throw failureFor(response, payload);
}

/** @param {Response} response */
async function readJson(response) {
  const text = await response.text().catch(() => "");
  if (!text) {
    return undefined;
  }
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

/**
 * @param {Response} response
 * @param {unknown} payload
 */
function failureFor(response, payload) {
  const error = isErrorBody(payload) ? payload.error : null;
  const code = error?.code;
  const message = typeof error?.message === "string" ? error.message : null;

  if (response.status === 429) {
    const retry = Number.parseInt(response.headers.get("Retry-After") ?? "", 10);
    return new ApiFailure("rate_limited", message ?? "Too many requests. Please wait a moment.", {
      code: code ?? "RATE_LIMITED",
      status: 429,
      retryAfterSeconds: Number.isFinite(retry) && retry > 0 ? retry : null,
    });
  }
  if (response.status >= 500 || code === "SERVICE_UNAVAILABLE" || code === "QUEUE_FULL" || code === "STORAGE_FULL") {
    return new ApiFailure("unavailable", message ?? "The service is temporarily unavailable.", {
      code: code ?? "SERVICE_UNAVAILABLE",
      status: response.status,
    });
  }
  if (message && code) {
    return new ApiFailure("rejected", message, { code, status: response.status });
  }
  return new ApiFailure("malformed", "The server returned an unexpected error.", { status: response.status });
}

/** @param {unknown} value @returns {value is { error: { code?: string, message?: string } }} */
function isErrorBody(value) {
  return Boolean(value && typeof value === "object" && "error" in value && value.error && typeof value.error === "object");
}

/**
 * Minimal structural check so a broken or hostile response cannot drive the UI into an
 * inconsistent state (e.g. a download action with no tool behind it).
 * @param {unknown} value
 */
export function validateAnalysis(value) {
  const v = /** @type {Record<string, unknown>} */ (value);
  const ok =
    value !== null &&
    typeof value === "object" &&
    typeof v.normalized_url === "string" &&
    typeof v.resource_type === "string" &&
    ANALYSIS_STATUSES.has(/** @type {string} */ (v.status)) &&
    SOURCE_KINDS.has(/** @type {string} */ (v.source_kind)) &&
    Array.isArray(v.tools) &&
    v.tools.every((t) => typeof t === "string") &&
    (v.resource_counts === undefined || isCountMap(v.resource_counts)) &&
    (v.status === "ok" || isReason(v.reason));
  if (!ok) {
    throw new ApiFailure("malformed", "The server returned a response the extension could not read.");
  }
  return value;
}

/** @param {unknown} value */
function isCountMap(value) {
  return (
    value !== null &&
    typeof value === "object" &&
    Object.values(value).every((n) => Number.isInteger(n) && n >= 0)
  );
}

/** @param {unknown} value */
function isReason(value) {
  const r = /** @type {Record<string, unknown>} */ (value);
  return value !== null && typeof value === "object" && typeof r.code === "string" && typeof r.message === "string";
}
