import type { MetadataRoute } from "next";

import { TOOL_IDS } from "@/lib/catalogue";
import { SITE_URL } from "@/lib/env";

export default function sitemap(): MetadataRoute.Sitemap {
  const staticRoutes = [
    "",
    "/tools",
    "/about",
    "/extension",
    "/privacy",
    "/terms",
    "/copyright",
    "/security",
    "/contact",
  ];

  return [
    ...staticRoutes.map((path) => ({
      url: `${SITE_URL}${path || "/"}`,
      changeFrequency: "weekly" as const,
      priority: path === "" ? 1 : 0.6,
    })),
    ...TOOL_IDS.map((id) => ({
      url: `${SITE_URL}/tools/${id}`,
      changeFrequency: "monthly" as const,
      priority: 0.5,
    })),
  ];
}
