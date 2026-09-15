import assert from "node:assert/strict";
import { test } from "node:test";

import { ApiFailure, analyzeUrl, validateAnalysis } from "../../src/api.js";

const ORIGIN = "https://example.test";
const PAGE = "https://news.example.org/story";

const okAnalysis = {
  normalized_url: PAGE,
  source_kind: "webpage",
  resource_type: "WEBPAGE",
  status: "ok",
  tools: ["website-image-gallery"],
  resource_counts: { IMAGE: 3 },
};

/** Builds a fetch stand-in that records the request and returns `response`. */
function fakeFetch(response, calls = []) {
  return async (url, init) => {
    calls.push({ url, init });
    if (response instanceof Error) {
      throw response;
    }
    return response;
  };
}

const json = (status, body, headers = {}) =>
  new Response(typeof body === "string" ? body : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

async function failureOf(promise) {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  assert.fail("expected the request to fail");
}

test("sends only the page URL, without credentials, to the analyze endpoint", async () => {
  const calls = [];
  const result = await analyzeUrl(ORIGIN, PAGE, { fetchImpl: fakeFetch(json(200, okAnalysis), calls) });
  assert.equal(result.status, "ok");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, `${ORIGIN}/api/v1/analyze`);
  assert.equal(calls[0].init.method, "POST");
  assert.equal(calls[0].init.credentials, "omit");
  assert.deepEqual(JSON.parse(calls[0].init.body), { url: PAGE });
});

test("rate limiting carries Retry-After", async () => {
  const error = await failureOf(
    analyzeUrl(ORIGIN, PAGE, {
      fetchImpl: fakeFetch(
        json(429, { error: { code: "RATE_LIMITED", message: "Slow down." } }, { "Retry-After": "17" }),
      ),
    }),
  );
  assert.ok(error instanceof ApiFailure);
  assert.equal(error.kind, "rate_limited");
  assert.equal(error.retryAfterSeconds, 17);
  assert.equal(error.message, "Slow down.");
});

test("server-side SSRF rejection is reported with the server's code and message", async () => {
  const body = { error: { code: "BLOCKED_TARGET", message: "URLs pointing to private addresses cannot be processed." } };
  const error = await failureOf(analyzeUrl(ORIGIN, PAGE, { fetchImpl: fakeFetch(json(400, body)) }));
  assert.equal(error.kind, "rejected");
  assert.equal(error.code, "BLOCKED_TARGET");
  assert.equal(error.message, body.error.message);
});

test("5xx and storage/queue pressure are 'unavailable'", async () => {
  for (const [status, body] of [
    [500, "Internal Server Error"],
    [502, ""],
    [503, { error: { code: "STORAGE_FULL", message: "Out of space." } }],
  ]) {
    const error = await failureOf(analyzeUrl(ORIGIN, PAGE, { fetchImpl: fakeFetch(json(status, body)) }));
    assert.equal(error.kind, "unavailable", `status ${status}`);
  }
});

test("network failure and timeout are distinguished", async () => {
  const network = await failureOf(analyzeUrl(ORIGIN, PAGE, { fetchImpl: fakeFetch(new TypeError("Failed to fetch")) }));
  assert.equal(network.kind, "network");

  const hanging = (url, init) =>
    new Promise((_, reject) => init.signal.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError"))));
  const timeout = await failureOf(analyzeUrl(ORIGIN, PAGE, { fetchImpl: hanging, timeoutMs: 20 }));
  assert.equal(timeout.kind, "timeout");
});

test("malformed responses never reach the UI as data", async () => {
  for (const body of [
    "<html>not json</html>",
    "",
    { status: "ok" },
    { ...okAnalysis, status: "maybe" },
    { ...okAnalysis, tools: "website-image-gallery" },
    { ...okAnalysis, resource_counts: { IMAGE: -1 } },
    { ...okAnalysis, status: "restricted" }, // restricted without a reason
  ]) {
    const error = await failureOf(analyzeUrl(ORIGIN, PAGE, { fetchImpl: fakeFetch(json(200, body)) }));
    assert.equal(error.kind, "malformed", JSON.stringify(body));
  }
});

test("an error body without code/message is malformed, not trusted", async () => {
  const error = await failureOf(analyzeUrl(ORIGIN, PAGE, { fetchImpl: fakeFetch(json(400, { detail: "x" })) }));
  assert.equal(error.kind, "malformed");
});

test("validateAnalysis accepts restricted responses with a reason", () => {
  const restricted = {
    ...okAnalysis,
    status: "restricted",
    tools: [],
    reason: { code: "SOURCE_REQUIRES_AUTH", message: "Sign-in required." },
  };
  assert.equal(validateAnalysis(restricted), restricted);
});
