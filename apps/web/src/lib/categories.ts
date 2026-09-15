import {
  FileText,
  Globe,
  Image as ImageIcon,
  Music,
  Video,
  Wrench,
  type LucideIcon,
} from "lucide-react";

import { TOOL_CATALOGUE, type CatalogueTool, type ToolCategory } from "@/lib/catalogue";

export type CategoryMeta = {
  id: ToolCategory;
  label: string;
  blurb: string;
  icon: LucideIcon;
  /** CSS colour variable for this category's identity hue. */
  hue: string;
};

export const CATEGORIES: readonly CategoryMeta[] = [
  {
    id: "video",
    label: "Video",
    blurb: "Save, convert, compress and trim public video.",
    icon: Video,
    hue: "var(--cat-video)",
  },
  {
    id: "audio",
    label: "Audio",
    blurb: "Extract, convert and shrink audio tracks.",
    icon: Music,
    hue: "var(--cat-audio)",
  },
  {
    id: "image",
    label: "Image",
    blurb: "Compress, resize and convert images.",
    icon: ImageIcon,
    hue: "var(--cat-image)",
  },
  {
    id: "pdf",
    label: "PDF",
    blurb: "Merge, split, compress and render PDFs.",
    icon: FileText,
    hue: "var(--cat-pdf)",
  },
  {
    id: "web",
    label: "Web",
    blurb: "Find the media a public page references.",
    icon: Globe,
    hue: "var(--cat-web)",
  },
  {
    id: "utility",
    label: "Utilities",
    blurb: "QR codes, screenshots, favicons and metadata.",
    icon: Wrench,
    hue: "var(--cat-utility)",
  },
];

export function categoryMeta(id: ToolCategory): CategoryMeta {
  return CATEGORIES.find((item) => item.id === id) ?? CATEGORIES[0];
}

export function toolsInCategory(id: ToolCategory, tools: CatalogueTool[] = TOOL_CATALOGUE) {
  return tools.filter((tool) => tool.category === id);
}

/** Featured tools, in a deliberate order (not alphabetical). */
export const FEATURED_TOOL_IDS = [
  "video-downloader",
  "video-to-mp3",
  "image-compressor",
  "pdf-merger",
  "website-image-gallery",
  "qr-generator",
] as const;

/** Short verb-led names for quick actions. */
export const QUICK_ACTIONS: ReadonlyArray<{ id: string; label: string }> = [
  { id: "video-to-mp3", label: "Video → MP3" },
  { id: "video-downloader", label: "Save a video" },
  { id: "image-compressor", label: "Shrink an image" },
  { id: "image-to-webp", label: "Image → WebP" },
  { id: "pdf-merger", label: "Merge PDFs" },
  { id: "pdf-compressor", label: "Compress a PDF" },
  { id: "webpage-screenshot", label: "Screenshot a page" },
  { id: "qr-generator", label: "Make a QR code" },
];

/** Plain-language input labels. */
export function inputLabels(tool: CatalogueTool): string[] {
  const labels: string[] = [];
  if (tool.inputs.includes("url")) labels.push("Link");
  if (tool.inputs.includes("upload") || tool.inputs.includes("uploads")) {
    labels.push(tool.inputs.includes("uploads") ? "Files" : "File");
  }
  if (tool.inputs.includes("text")) labels.push("Text");
  return labels;
}

/**
 * "Video to MP3" → { from: "Video", to: "MP3" }. Purely descriptive (from the tool's own
 * name); it never implies what a particular source supports.
 */
export function transformOf(tool: CatalogueTool | undefined): { from: string; to: string } | null {
  if (!tool) return null;
  const match = /^(.+?) to (.+)$/i.exec(tool.name);
  return match ? { from: match[1], to: match[2] } : null;
}

/** Motion metaphor for a tool: drives the processing visual. */
export type ToolMetaphor = "download" | "convert" | "compress" | "extract" | "render" | "inspect";

export function metaphorOf(tool: CatalogueTool | undefined): ToolMetaphor {
  const id = tool?.id ?? "";
  if (id.includes("compress")) return "compress";
  if (id.includes("downloader") || id === "file-downloader") return "download";
  if (/finder|extractor|gallery|thumbnail|to-text|splitter/.test(id)) return "extract";
  if (/screenshot|url-to-pdf|qr-generator|to-images/.test(id)) return "render";
  if (/metadata|analyzer|reader/.test(id)) return "inspect";
  return "convert";
}
