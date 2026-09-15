"use client";

import {
  Archive,
  File as FileIcon,
  FileText,
  Globe,
  Image as ImageIcon,
  Link2,
  Music,
  Sparkles,
  Upload,
  Video,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import type { ResourceType, URLAnalysis, UploadView } from "@/lib/api";
import { cn } from "@/lib/cn";
import { copy, noteLabel } from "@/lib/copy";
import { formatBytes, formatDuration, humanizeKey, isSafeHttpUrl } from "@/lib/format";

const TYPE_ICON: Record<ResourceType, LucideIcon> = {
  VIDEO: Video,
  AUDIO: Music,
  IMAGE: ImageIcon,
  PDF: FileText,
  DOCUMENT: FileText,
  WEBPAGE: Globe,
  ARCHIVE: Archive,
  UNKNOWN: FileIcon,
};

const TYPE_LABEL: Record<ResourceType, string> = {
  VIDEO: "Video",
  AUDIO: "Audio",
  IMAGE: "Image",
  PDF: "PDF",
  DOCUMENT: "Document",
  WEBPAGE: "Web page",
  ARCHIVE: "Archive",
  UNKNOWN: "Unknown type",
};

const SOURCE_LABEL: Record<string, string> = {
  direct: "Direct file",
  webpage: "Web page",
  platform: "Public platform",
};

/**
 * What the server detected. Everything here comes from the API response; the panel only
 * arranges it. Sections enter in sequence: source → details → capabilities.
 */
export function AnalysisResult({
  analysis,
  upload,
}: {
  analysis?: URLAnalysis | null;
  upload?: UploadView | null;
}) {
  const [thumbLoaded, setThumbLoaded] = useState(false);
  if (!analysis && !upload) {
    return null;
  }

  const resourceType = analysis?.resource_type || upload?.resource_type || "UNKNOWN";
  const TypeIcon = TYPE_ICON[resourceType] ?? FileIcon;
  const title =
    analysis?.title || analysis?.filename || upload?.filename || copy.widget.resultsHeading;
  const thumbnail = analysis?.thumbnail;
  const hasThumb = Boolean(thumbnail && isSafeHttpUrl(thumbnail));
  const host = analysis ? hostOf(analysis.final_url || analysis.normalized_url) : null;
  const facts = [
    { label: copy.analysis.type, value: TYPE_LABEL[resourceType] },
    {
      label: copy.analysis.source,
      value: analysis
        ? (SOURCE_LABEL[analysis.source_kind] ?? analysis.source_kind)
        : "Your upload",
    },
    { label: copy.analysis.duration, value: formatDuration(analysis?.duration_seconds) },
    { label: copy.analysis.size, value: formatBytes(analysis?.size_bytes ?? upload?.size_bytes) },
    {
      label: copy.analysis.dimensions,
      value: analysis?.width && analysis?.height ? `${analysis.width}×${analysis.height}` : "",
    },
    { label: copy.analysis.mime, value: analysis?.mime_type || upload?.mime_type },
  ].filter((fact) => Boolean(fact.value));
  const resourceCounts = analysis ? Object.entries(analysis.resource_counts) : [];
  const capabilities = analysis?.capabilities ?? [];

  return (
    <section
      aria-label={copy.widget.resultsHeading}
      className="surface animate-scale-in overflow-hidden rounded-2xl"
    >
      <div className="border-border flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
        <div className="animate-fade-in flex min-w-0 items-center gap-2.5">
          <span
            aria-hidden="true"
            className="bg-accent-soft text-accent animate-pop grid size-8 place-items-center rounded-lg"
          >
            {analysis ? <Link2 className="size-4" /> : <Upload className="size-4" />}
          </span>
          <p className="text-sm">
            <span className="text-muted-foreground">Detected </span>
            <span className="font-semibold">{host ?? "your file"}</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {analysis?.platform ? <Badge variant="outline">{analysis.platform}</Badge> : null}
          <Badge>
            <TypeIcon aria-hidden="true" />
            {TYPE_LABEL[resourceType]}
          </Badge>
        </div>
      </div>

      <div className="grid gap-5 p-5 sm:grid-cols-[minmax(0,15rem)_1fr]">
        <div
          className={cn(
            "bg-muted relative grid aspect-video w-full place-items-center overflow-hidden rounded-xl",
            !hasThumb && "hidden sm:grid",
          )}
        >
          {hasThumb ? (
            // Remote platform thumbnails are not configured for next/image.
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={thumbnail!}
              alt=""
              onLoad={() => setThumbLoaded(true)}
              className={cn(
                "absolute inset-0 size-full object-cover transition-[opacity,transform] duration-700 ease-out",
                thumbLoaded ? "scale-100 opacity-100" : "scale-105 opacity-0",
              )}
            />
          ) : (
            <TypeIcon className="text-muted-foreground size-9" aria-hidden="true" />
          )}
        </div>
        <div className="animate-fade-up min-w-0 [--ad-delay:80ms]">
          <p className="font-display break-words text-lg font-bold leading-snug">{title}</p>
          {analysis?.description ? (
            <p className="text-muted-foreground mt-1.5 line-clamp-2 text-sm">
              {analysis.description}
            </p>
          ) : null}
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm lg:grid-cols-3">
            {facts.map((fact) => (
              <div key={fact.label} className="min-w-0">
                <dt className="text-muted-foreground text-xs font-semibold uppercase tracking-wide">
                  {fact.label}
                </dt>
                <dd className="break-words font-medium">{fact.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {capabilities.length ||
      resourceCounts.length ||
      analysis?.warnings?.length ||
      analysis?.restrictions?.length ? (
        <div className="border-border bg-background-alt/60 space-y-4 border-t px-5 py-4">
          {capabilities.length ? (
            <ChipRow
              title="What the server can do with it"
              icon={<Sparkles className="text-accent size-3.5" aria-hidden="true" />}
              items={capabilities.map(humanizeKey)}
              variant="default"
            />
          ) : null}
          {resourceCounts.length ? (
            <ChipRow
              title={copy.analysis.resources}
              items={resourceCounts.map(([key, count]) => `${humanizeKey(key)}: ${count}`)}
            />
          ) : null}
          {analysis?.warnings?.length ? (
            <ChipRow title={copy.analysis.warnings} items={analysis.warnings.map(noteLabel)} />
          ) : null}
          {analysis?.restrictions?.length ? (
            <ChipRow
              title={copy.analysis.restrictions}
              items={analysis.restrictions.map(noteLabel)}
              variant="warning"
            />
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function hostOf(value: string | null | undefined) {
  if (!value) return null;
  try {
    return new URL(value).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function ChipRow({
  title,
  items,
  icon,
  variant = "outline",
}: {
  title: string;
  items: string[];
  icon?: React.ReactNode;
  variant?: "outline" | "warning" | "default";
}) {
  return (
    <div>
      <p className="text-muted-foreground mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide">
        {icon}
        {title}
      </p>
      <ul className="flex flex-wrap gap-2">
        {items.map((item, index) => (
          <li key={item} className="animate-fade-up" style={{ ["--i" as string]: index }}>
            <Badge variant={variant}>{item}</Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}
