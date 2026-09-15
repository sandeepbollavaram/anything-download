import type { MediaFormat } from "@/lib/api";
import { getCatalogueTool } from "@/lib/catalogue";

export type OptionField =
  | {
      key: string;
      kind: "select";
      label: string;
      options: Array<{ value: string; label: string }>;
      defaultValue: string;
    }
  | {
      key: string;
      kind: "number";
      label: string;
      min?: number;
      max?: number;
      step?: number;
      defaultValue: string;
    }
  | {
      key: string;
      kind: "text";
      label: string;
      placeholder?: string;
      defaultValue: string;
    }
  | {
      key: string;
      kind: "checkbox";
      label: string;
      defaultValue: boolean;
    };

const QUALITY = [
  { value: "high", label: "High" },
  { value: "balanced", label: "Balanced" },
  { value: "small", label: "Smaller file" },
];

const LEVEL = [
  { value: "light", label: "Light" },
  { value: "medium", label: "Medium" },
  { value: "strong", label: "Strong" },
];

const VIDEO_BITRATE = [
  { value: "96", label: "96 kbps" },
  { value: "128", label: "128 kbps" },
  { value: "192", label: "192 kbps" },
  { value: "256", label: "256 kbps" },
  { value: "320", label: "320 kbps" },
];

const AUDIO_BITRATE = [
  { value: "64", label: "64 kbps" },
  { value: "96", label: "96 kbps" },
  { value: "128", label: "128 kbps" },
  { value: "160", label: "160 kbps" },
  { value: "192", label: "192 kbps" },
  { value: "256", label: "256 kbps" },
  { value: "320", label: "320 kbps" },
];

const IMAGE_TARGETS = [
  { value: "jpeg", label: "JPEG" },
  { value: "png", label: "PNG" },
  { value: "webp", label: "WebP" },
  { value: "avif", label: "AVIF" },
  { value: "gif", label: "GIF" },
  { value: "bmp", label: "BMP" },
  { value: "tiff", label: "TIFF" },
];

const AUDIO_TARGETS = [
  { value: "mp3", label: "MP3" },
  { value: "wav", label: "WAV" },
  { value: "aac", label: "AAC" },
  { value: "m4a", label: "M4A" },
  { value: "ogg", label: "OGG" },
  { value: "flac", label: "FLAC" },
];

const FIT = [
  { value: "contain", label: "Contain" },
  { value: "cover", label: "Cover" },
  { value: "exact", label: "Exact" },
];

const SPLIT_MODE = [
  { value: "ranges", label: "Page ranges" },
  { value: "each", label: "Each page" },
  { value: "chunks", label: "Fixed-size chunks" },
];

const IMAGE_FORMATS = [
  { value: "png", label: "PNG" },
  { value: "jpg", label: "JPEG" },
  { value: "webp", label: "WebP" },
];

const QR_FORMAT = [
  { value: "png", label: "PNG" },
  { value: "svg", label: "SVG" },
];

const QR_ERROR = [
  { value: "L", label: "L (low)" },
  { value: "M", label: "M (medium)" },
  { value: "Q", label: "Q (quartile)" },
  { value: "H", label: "H (high)" },
];

const PAGE_SIZE_PRINT = [
  { value: "A4", label: "A4" },
  { value: "Letter", label: "Letter" },
];

const PAGE_SIZE_IMAGE = [
  { value: "fit", label: "Fit image" },
  { value: "a4", label: "A4" },
  { value: "letter", label: "Letter" },
];

function formatOptions(formats: MediaFormat[] | undefined) {
  if (!formats?.length) {
    return [{ value: "best", label: "Best available" }];
  }
  return formats.map((format) => ({
    value: format.id,
    label: format.label,
  }));
}

export function optionFieldsForTool(toolId: string, formats?: MediaFormat[]): OptionField[] {
  const fields: OptionField[] = [];
  const catalogue = getCatalogueTool(toolId);
  const hasFormat =
    Boolean(formats?.length) ||
    ["video-downloader", "audio-downloader", "video-to-mp3", "video-to-wav"].includes(toolId) ||
    Boolean(catalogue?.inputs.includes("url"));

  const commonFormat = (
    defaultValue = formats?.[0]?.id ?? "best",
  ): Extract<OptionField, { kind: "select" }> => ({
    key: "format",
    kind: "select",
    label: "Format",
    options: formatOptions(formats),
    defaultValue,
  });

  switch (toolId) {
    case "video-downloader":
    case "audio-downloader":
    case "file-downloader":
    case "image-downloader":
    case "pdf-downloader":
      fields.push(commonFormat());
      break;
    case "video-to-mp3":
      if (hasFormat) fields.push(commonFormat("audio"));
      fields.push({
        key: "bitrate_kbps",
        kind: "select",
        label: "Bitrate",
        options: VIDEO_BITRATE,
        defaultValue: "192",
      });
      break;
    case "video-to-wav":
      if (hasFormat) fields.push(commonFormat("audio"));
      break;
    case "video-to-mp4":
      if (hasFormat) fields.push(commonFormat());
      fields.push({
        key: "quality",
        kind: "select",
        label: "Quality",
        options: QUALITY,
        defaultValue: "balanced",
      });
      break;
    case "video-compressor":
      if (hasFormat) fields.push(commonFormat());
      fields.push({
        key: "level",
        kind: "select",
        label: "Compression level",
        options: LEVEL,
        defaultValue: "medium",
      });
      break;
    case "video-to-gif":
      if (hasFormat) fields.push(commonFormat());
      fields.push(
        {
          key: "start_seconds",
          kind: "number",
          label: "Start (seconds)",
          min: 0,
          defaultValue: "0",
        },
        {
          key: "duration_seconds",
          kind: "number",
          label: "Duration (seconds)",
          min: 0.1,
          max: 15,
          step: 0.5,
          defaultValue: "5",
        },
        {
          key: "fps",
          kind: "number",
          label: "Frames per second",
          min: 1,
          max: 30,
          defaultValue: "12",
        },
        { key: "width", kind: "number", label: "Width", min: 32, max: 1280, defaultValue: "480" },
      );
      break;
    case "video-thumbnail":
      if (hasFormat) fields.push(commonFormat("480p"));
      fields.push(
        {
          key: "at_seconds",
          kind: "number",
          label: "Timestamp (seconds)",
          min: 0,
          defaultValue: "",
        },
        {
          key: "image_format",
          kind: "select",
          label: "Image format",
          options: IMAGE_FORMATS,
          defaultValue: "jpg",
        },
        { key: "width", kind: "number", label: "Width", min: 16, max: 3840, defaultValue: "" },
      );
      break;
    case "image-compressor":
      fields.push(
        { key: "quality", kind: "number", label: "Quality", min: 10, max: 95, defaultValue: "75" },
        { key: "keep_metadata", kind: "checkbox", label: "Keep metadata", defaultValue: false },
      );
      break;
    case "image-converter":
      fields.push(
        {
          key: "target",
          kind: "select",
          label: "Output format",
          options: IMAGE_TARGETS,
          defaultValue: "png",
        },
        { key: "quality", kind: "number", label: "Quality", min: 10, max: 100, defaultValue: "85" },
        { key: "keep_metadata", kind: "checkbox", label: "Keep metadata", defaultValue: false },
      );
      break;
    case "image-resizer":
      fields.push(
        { key: "width", kind: "number", label: "Width", min: 1, max: 10000, defaultValue: "" },
        { key: "height", kind: "number", label: "Height", min: 1, max: 10000, defaultValue: "" },
        {
          key: "percent",
          kind: "number",
          label: "Scale percent",
          min: 1,
          max: 400,
          defaultValue: "50",
        },
        { key: "fit", kind: "select", label: "Fit", options: FIT, defaultValue: "contain" },
        { key: "keep_metadata", kind: "checkbox", label: "Keep metadata", defaultValue: false },
      );
      break;
    case "image-to-webp":
      fields.push(
        { key: "quality", kind: "number", label: "Quality", min: 10, max: 100, defaultValue: "80" },
        { key: "lossless", kind: "checkbox", label: "Lossless", defaultValue: false },
        { key: "keep_metadata", kind: "checkbox", label: "Keep metadata", defaultValue: false },
      );
      break;
    case "image-to-pdf":
      fields.push({
        key: "page_size",
        kind: "select",
        label: "Page size",
        options: PAGE_SIZE_IMAGE,
        defaultValue: "fit",
      });
      break;
    case "pdf-compressor":
    case "audio-compressor":
      if (toolId === "audio-compressor" && hasFormat) {
        fields.push(commonFormat("audio"));
      }
      fields.push({
        key: "level",
        kind: "select",
        label: "Compression level",
        options: LEVEL,
        defaultValue: "medium",
      });
      break;
    case "pdf-splitter":
      fields.push(
        {
          key: "mode",
          kind: "select",
          label: "Split mode",
          options: SPLIT_MODE,
          defaultValue: "ranges",
        },
        {
          key: "pages",
          kind: "text",
          label: "Pages",
          placeholder: "1-3,5,8-",
          defaultValue: "",
        },
        {
          key: "chunk_size",
          kind: "number",
          label: "Pages per file",
          min: 1,
          max: 500,
          defaultValue: "10",
        },
      );
      break;
    case "pdf-to-text":
      fields.push({
        key: "pages",
        kind: "text",
        label: "Pages",
        placeholder: "1-5 (empty = all)",
        defaultValue: "",
      });
      break;
    case "pdf-to-images":
      fields.push(
        {
          key: "format",
          kind: "select",
          label: "Image format",
          options: IMAGE_FORMATS,
          defaultValue: "png",
        },
        { key: "dpi", kind: "number", label: "DPI", min: 36, max: 300, defaultValue: "144" },
        {
          key: "pages",
          kind: "text",
          label: "Pages",
          placeholder: "1-5 (empty = all)",
          defaultValue: "",
        },
      );
      break;
    case "url-to-pdf":
      fields.push(
        {
          key: "page_size",
          kind: "select",
          label: "Page size",
          options: PAGE_SIZE_PRINT,
          defaultValue: "A4",
        },
        { key: "landscape", kind: "checkbox", label: "Landscape", defaultValue: false },
        {
          key: "print_background",
          kind: "checkbox",
          label: "Print background",
          defaultValue: true,
        },
      );
      break;
    case "audio-converter":
      if (hasFormat) fields.push(commonFormat("audio"));
      fields.push(
        {
          key: "target",
          kind: "select",
          label: "Output format",
          options: AUDIO_TARGETS,
          defaultValue: "mp3",
        },
        {
          key: "bitrate_kbps",
          kind: "select",
          label: "Bitrate",
          options: AUDIO_BITRATE,
          defaultValue: "192",
        },
      );
      break;
    case "website-image-gallery":
      fields.push(
        {
          key: "max_images",
          kind: "number",
          label: "Maximum images",
          min: 1,
          max: 100,
          defaultValue: "30",
        },
        {
          key: "min_bytes",
          kind: "number",
          label: "Skip images smaller than (bytes)",
          min: 0,
          defaultValue: "5120",
        },
      );
      break;
    case "qr-generator":
      fields.push(
        {
          key: "format",
          kind: "select",
          label: "QR format",
          options: QR_FORMAT,
          defaultValue: "png",
        },
        { key: "scale", kind: "number", label: "Scale", min: 1, max: 40, defaultValue: "10" },
        { key: "border", kind: "number", label: "Border", min: 0, max: 16, defaultValue: "4" },
        {
          key: "error_correction",
          kind: "select",
          label: "Error correction",
          options: QR_ERROR,
          defaultValue: "M",
        },
      );
      break;
    case "webpage-screenshot":
      fields.push(
        { key: "width", kind: "number", label: "Width", min: 320, max: 1920, defaultValue: "1280" },
        {
          key: "height",
          kind: "number",
          label: "Height",
          min: 320,
          max: 1600,
          defaultValue: "800",
        },
        { key: "full_page", kind: "checkbox", label: "Capture the full page", defaultValue: false },
      );
      break;
    default:
      break;
  }

  return fields;
}

export function collectOptions(
  fields: OptionField[],
  values: Record<string, string | boolean>,
): Record<string, unknown> {
  const options: Record<string, unknown> = {};
  for (const field of fields) {
    const raw = values[field.key];
    if (field.kind === "checkbox") {
      options[field.key] = Boolean(raw);
      continue;
    }
    if (raw === undefined || raw === "") {
      continue;
    }
    if (field.kind === "number") {
      const num = Number(raw);
      if (!Number.isNaN(num)) {
        options[field.key] = num;
      }
      continue;
    }
    if (field.key === "bitrate_kbps") {
      options[field.key] = Number(raw);
      continue;
    }
    options[field.key] = raw;
  }
  return options;
}
