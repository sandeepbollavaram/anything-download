import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Plus_Jakarta_Sans } from "next/font/google";

import { BackToTop } from "@/components/back-to-top";
import { Footer } from "@/components/footer";
import { Header } from "@/components/header";
import { JsonLd } from "@/components/json-ld";
import { PwaRegister } from "@/components/pwa-register";
import { SkipLink } from "@/components/skip-link";
import { ThemeProvider } from "@/components/theme-provider";
import { copy } from "@/lib/copy";
import { SITE_NAME, SITE_URL } from "@/lib/env";
import { pageMetadata, siteJsonLd } from "@/lib/seo";

import "./globals.css";

// Body: a clean, highly legible sans for a tool people use daily.
const sans = Geist({
  subsets: ["latin"],
  variable: "--font-sans",
});

// Display: heavy geometric sans that matches the logo's wordmark.
const display = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["600", "700", "800"],
  variable: "--font-display",
});

const mono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  applicationName: SITE_NAME,
  ...pageMetadata({
    title: SITE_NAME,
    description: `${copy.brand.honest} ${copy.brand.positioning}`,
    path: "/",
  }),
  title: {
    default: `${SITE_NAME} | ${copy.brand.tagline}`,
    template: `%s · ${SITE_NAME}`,
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#050b19" },
  ],
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${sans.variable} ${display.variable} ${mono.variable} min-h-dvh font-sans`}>
        <ThemeProvider>
          <SkipLink />
          <div className="relative flex min-h-dvh flex-col overflow-x-clip">
            <span id="top-sentinel" aria-hidden="true" className="absolute left-0 top-0 h-2 w-px" />
            <span
              id="fold-sentinel"
              aria-hidden="true"
              className="absolute left-0 top-[120vh] h-px w-px"
            />
            <Header />
            <main id="main" tabIndex={-1} className="flex-1 outline-none">
              {children}
            </main>
            <Footer />
          </div>
          <BackToTop />
          <PwaRegister />
          <JsonLd data={siteJsonLd()} />
        </ThemeProvider>
      </body>
    </html>
  );
}
