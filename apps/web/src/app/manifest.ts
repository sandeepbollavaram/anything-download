import type { MetadataRoute } from "next";

import { copy } from "@/lib/copy";
import { SITE_NAME } from "@/lib/env";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE_NAME,
    short_name: "Anything DL",
    description: copy.brand.honest,
    start_url: "/",
    display: "standalone",
    background_color: "#f7f6f1",
    theme_color: "#0b1b3a",
    lang: "en",
    icons: [
      { src: "/brand/mark-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/brand/mark-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    ],
  };
}
