export const SITE_NAME = process.env.NEXT_PUBLIC_SITE_NAME || "Anything Download";

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(
  /\/$/,
  "",
);

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);

export function absoluteUrl(path = "/") {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${SITE_URL}${normalized}`;
}

/** Browser calls go same-origin through the Next rewrite. Server calls the API directly. */
export function getApiOrigin(): string {
  if (typeof window === "undefined") {
    return API_URL;
  }
  return "";
}

export function apiPath(path: string): string {
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${getApiOrigin()}/api/v1${suffix}`;
}
