import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Next's /api rewrite proxy silently truncates request bodies above
// experimental.proxyClientMaxBodySize (10 MB by default) and the upstream request
// then hangs until the proxy times out, so every larger upload failed. Allow up to
// the API's own upload limit plus headroom, and let the API enforce the real limit
// (it rejects an oversized Content-Length up front with 413).
// Next also buffers the proxied body in memory up to this size, which is why
// production should route /api to the API at the reverse proxy, not through Next.
const MAX_UPLOAD_MB = Number(process.env.AD_MAX_UPLOAD_SIZE_MB) || 200;
const PROXY_MAX_BODY_BYTES = (MAX_UPLOAD_MB + 1) * 1024 * 1024;
const configDir = path.dirname(fileURLToPath(import.meta.url));

// script-src needs 'unsafe-inline': Next.js injects inline bootstrap scripts on every
// page, and without it React never hydrates (the site renders but is dead to clicks).
// The alternative, a per-request nonce from middleware, would force all 54 static
// routes to render dynamically. What this policy still buys is the property that
// actually matters here: no third-party script origin can load at all, and this app
// ships no ads, analytics or CDN scripts. Thumbnails are hotlinked from arbitrary
// platform CDNs (validated as http(s) upstream), so img-src stays open to https:.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' https: data:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: CSP },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(configDir, "../.."),
  experimental: {
    proxyClientMaxBodySize: PROXY_MAX_BODY_BYTES,
  },
  images: {
    remotePatterns: [],
  },
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_URL.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
