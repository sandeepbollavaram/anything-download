import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { CategoryIcon } from "@/components/category-icon";
import { Badge } from "@/components/ui/badge";
import { categoryMeta, inputLabels } from "@/lib/categories";
import type { CatalogueTool } from "@/lib/catalogue";
import { cn } from "@/lib/cn";
import { copy } from "@/lib/copy";

export function ToolCard({
  tool,
  unavailable = false,
  catalogueOnly = false,
  featured = false,
  className,
  style,
}: {
  tool: CatalogueTool;
  unavailable?: boolean;
  catalogueOnly?: boolean;
  featured?: boolean;
  className?: string;
  style?: React.CSSProperties;
}) {
  const meta = categoryMeta(tool.category);
  return (
    <Link
      href={`/tools/${tool.id}`}
      data-tool-card
      style={{ ...style, ["--hue" as string]: meta.hue }}
      className={cn(
        "lift surface group relative flex h-full min-h-11 flex-col overflow-hidden rounded-2xl p-5 outline-offset-4",
        featured && "p-6",
        unavailable && "opacity-80",
        className,
      )}
    >
      {/* Hover preview: a soft wash in the category hue. */}
      <span
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-16 size-40 rounded-full opacity-0 blur-2xl transition-opacity duration-500 [background:color-mix(in_oklab,var(--hue)_22%,transparent)] group-hover:opacity-100 group-focus-visible:opacity-100"
      />
      <span className="relative flex items-start justify-between gap-3">
        <CategoryIcon
          category={tool.category}
          size={featured ? "lg" : "md"}
          className="group-hover:-rotate-6 group-hover:scale-105"
        />
        <ArrowUpRight
          className="text-muted-foreground size-5 shrink-0 transition-[transform,color] duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-[color:var(--hue)]"
          aria-hidden="true"
        />
      </span>
      <span
        className={cn(
          "font-display relative mt-4 block font-bold",
          featured ? "text-lg" : "text-base",
        )}
      >
        {tool.name}
      </span>
      <span className="text-muted-foreground relative mt-1 block flex-1 text-sm">{tool.short}</span>
      <span className="relative mt-4 flex flex-wrap items-center gap-1.5">
        {inputLabels(tool).map((label) => (
          <span
            key={label}
            className="bg-muted text-muted-foreground rounded-md px-1.5 py-0.5 text-[11px] font-semibold"
          >
            {label}
          </span>
        ))}
        {unavailable ? <Badge variant="warning">{copy.tools.unavailable}</Badge> : null}
        {catalogueOnly ? <Badge variant="outline">Catalogue</Badge> : null}
      </span>
    </Link>
  );
}
