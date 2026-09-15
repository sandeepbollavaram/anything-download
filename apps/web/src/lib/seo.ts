import type { Metadata } from "next";

import { getCatalogueTool, type CatalogueTool } from "@/lib/catalogue";
import { copy } from "@/lib/copy";
import { absoluteUrl, SITE_NAME, SITE_URL } from "@/lib/env";

export function pageMetadata(input: {
  title: string;
  description: string;
  path: string;
  index?: boolean;
}): Metadata {
  const url = absoluteUrl(input.path);
  const title = input.title === SITE_NAME ? input.title : `${input.title} · ${SITE_NAME}`;
  return {
    title: input.title,
    description: input.description,
    alternates: { canonical: url },
    robots: input.index === false ? { index: false, follow: true } : undefined,
    openGraph: {
      title,
      description: input.description,
      url,
      siteName: SITE_NAME,
      type: "website",
      locale: "en",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description: input.description,
    },
  };
}

export function toolMetadata(tool: CatalogueTool): Metadata {
  return pageMetadata({
    title: tool.name,
    description: tool.description,
    path: `/tools/${tool.id}`,
  });
}

export function toolFromSlug(slug: string): CatalogueTool | undefined {
  return getCatalogueTool(slug);
}

export function siteJsonLd() {
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "Organization",
        "@id": `${SITE_URL}/#organization`,
        name: SITE_NAME,
        url: SITE_URL,
      },
      {
        "@type": "WebSite",
        "@id": `${SITE_URL}/#website`,
        name: SITE_NAME,
        url: SITE_URL,
        description: copy.brand.honest,
        publisher: { "@id": `${SITE_URL}/#organization` },
        inLanguage: "en",
      },
      {
        "@type": "SoftwareApplication",
        "@id": `${SITE_URL}/#app`,
        name: SITE_NAME,
        applicationCategory: "UtilitiesApplication",
        operatingSystem: "Web",
        offers: {
          "@type": "Offer",
          price: "0",
          priceCurrency: "USD",
        },
        description: copy.brand.honest,
        url: SITE_URL,
        publisher: { "@id": `${SITE_URL}/#organization` },
      },
    ],
  };
}

export function toolJsonLd(tool: CatalogueTool) {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: `${tool.name} · ${SITE_NAME}`,
    applicationCategory: "UtilitiesApplication",
    operatingSystem: "Web",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
    },
    description: tool.description,
    url: absoluteUrl(`/tools/${tool.id}`),
    isPartOf: {
      "@type": "WebSite",
      name: SITE_NAME,
      url: SITE_URL,
    },
  };
}
