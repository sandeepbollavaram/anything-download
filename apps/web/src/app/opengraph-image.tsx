import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { ImageResponse } from "next/og";

import { copy } from "@/lib/copy";
import { SITE_NAME } from "@/lib/env";

export const alt = SITE_NAME;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function OpenGraphImage() {
  const mark = await readFile(join(process.cwd(), "public/brand/mark-512.png"));
  const markSrc = `data:image/png;base64,${mark.toString("base64")}`;

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        gap: 64,
        padding: 80,
        backgroundColor: "#f7f6f1",
        color: "#0b1b3a",
      }}
    >
      <div
        style={{
          display: "flex",
          padding: 24,
          backgroundColor: "#ffffff",
          border: "6px solid #0b1b3a",
          borderRadius: 40,
          boxShadow: "14px 14px 0 0 #0b1b3a",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={markSrc} width={260} height={260} alt="" />
      </div>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <div
          style={{
            fontSize: 28,
            fontWeight: 700,
            letterSpacing: 3,
            textTransform: "uppercase",
            color: "#4a5468",
          }}
        >
          {copy.brand.tagline}
        </div>
        <div
          style={{ display: "flex", fontSize: 88, fontWeight: 800, marginTop: 12, lineHeight: 1 }}
        >
          Anything&nbsp;<span style={{ color: "#1244c7" }}>Download</span>
        </div>
        <div style={{ fontSize: 30, marginTop: 28, maxWidth: 680, color: "#4a5468" }}>
          {copy.brand.positioning}
        </div>
      </div>
    </div>,
    size,
  );
}
