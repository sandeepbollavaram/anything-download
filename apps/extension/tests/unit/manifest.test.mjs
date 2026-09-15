/**
 * Guards the extension's privacy promises at the manifest and source level, so a
 * permission or remote-code change cannot slip in unnoticed.
 */
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const SRC = fileURLToPath(new URL("../../src/", import.meta.url));
const manifest = JSON.parse(readFileSync(join(SRC, "manifest.json"), "utf8"));

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

test("Manifest V3 with only the minimum permissions", () => {
  assert.equal(manifest.manifest_version, 3);
  assert.deepEqual([...manifest.permissions].sort(), ["activeTab", "contextMenus", "storage"]);
  for (const forbidden of ["tabs", "history", "cookies", "webRequest", "scripting", "downloads", "<all_urls>", "debugger", "management"]) {
    assert.ok(!manifest.permissions.includes(forbidden), `must not request ${forbidden}`);
  }
});

test("host access is limited to the service; broader access is optional and per-origin", () => {
  assert.deepEqual(manifest.host_permissions, ["https://anythingdownload.in/*"]);
  assert.ok(!JSON.stringify(manifest.host_permissions).includes("<all_urls>"));
  assert.ok(!manifest.content_scripts, "no content scripts: pages are never read or modified");
  assert.ok(!manifest.web_accessible_resources, "no extension pages are exposed to websites");
});

test("extension pages allow no remote or inline code", () => {
  const csp = manifest.content_security_policy.extension_pages;
  assert.match(csp, /script-src 'self'(;|$)/);
  assert.doesNotMatch(csp, /unsafe-eval|unsafe-inline|wasm-unsafe-eval/);
  assert.match(csp, /object-src 'none'/);
});

test("no remote scripts, eval, innerHTML or analytics in the source", () => {
  for (const path of files(SRC)) {
    if (!/\.(js|html)$/.test(path)) {
      continue;
    }
    const text = readFileSync(path, "utf8");
    assert.doesNotMatch(text, /<script[^>]+src=["']https?:/i, `${path}: remote script`);
    assert.doesNotMatch(text, /\beval\(|new Function\(/, `${path}: dynamic code`);
    assert.doesNotMatch(text, /\.innerHTML\s*=|insertAdjacentHTML|outerHTML\s*=/, `${path}: HTML injection sink`);
    assert.doesNotMatch(text, /google-analytics|googletagmanager|segment\.io|mixpanel|sentry/i, `${path}: tracking`);
    assert.doesNotMatch(text, /document\.cookie|chrome\.cookies/, `${path}: cookie access`);
  }
});

test("every icon the manifest references exists", () => {
  const icons = { ...manifest.icons, ...manifest.action.default_icon };
  for (const path of Object.values(icons)) {
    assert.ok(statSync(join(SRC, path)).size > 0, path);
  }
});
