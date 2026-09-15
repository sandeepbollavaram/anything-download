import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { CategoryIcon } from "@/components/category-icon";
import { Container } from "@/components/container";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "@/components/page-hero";
import { CATEGORIES, toolsInCategory } from "@/lib/categories";
import { cn } from "@/lib/cn";
import { copy } from "@/lib/copy";

/** Bento grid: the two biggest categories get large tiles; the rest fill in around them. */
const LAYOUT: Record<string, string> = {
  video: "sm:col-span-2 lg:row-span-2",
  audio: "",
  image: "",
  pdf: "sm:col-span-2",
  web: "sm:col-span-2",
  utility: "sm:col-span-2",
};

export function Ecosystem() {
  return (
    <Container as="section" aria-labelledby="ecosystem-heading" className="py-16 sm:py-24">
      <SectionHeading
        id="ecosystem-heading"
        eyebrow={copy.home.ecosystemEyebrow}
        title={copy.home.ecosystemTitle}
        lead={copy.home.ecosystemLead}
      />
      <ul className="mt-12 grid auto-rows-[minmax(11rem,auto)] gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {CATEGORIES.map((category, index) => {
          const tools = toolsInCategory(category.id);
          const large = category.id === "video";
          const tall = category.id === "pdf" || category.id === "utility";
          return (
            <Reveal as="li" key={category.id} index={index} className={cn(LAYOUT[category.id])}>
              <Link
                href={`/tools#${category.id}`}
                style={{ ["--hue" as string]: category.hue }}
                className="lift surface group relative flex h-full flex-col overflow-hidden rounded-3xl p-6"
              >
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -bottom-24 -right-24 size-72 rounded-full opacity-50 blur-3xl transition-opacity duration-500 [background:color-mix(in_oklab,var(--hue)_20%,transparent)] group-hover:opacity-100"
                />
                <span className="relative flex items-start justify-between gap-4">
                  <CategoryIcon
                    category={category.id}
                    size={large ? "lg" : "md"}
                    className="group-hover:-rotate-6 group-hover:scale-110"
                  />
                  <span className="text-muted-foreground flex items-center gap-1 font-mono text-xs font-bold">
                    {tools.length} tools
                    <ArrowUpRight
                      className="size-4 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-[color:var(--hue)]"
                      aria-hidden="true"
                    />
                  </span>
                </span>
                <h3
                  className={cn(
                    "font-display relative mt-auto pt-6 font-extrabold",
                    large ? "text-3xl sm:text-4xl" : "text-xl",
                  )}
                >
                  {category.label}
                </h3>
                <p className="text-muted-foreground relative mt-1 text-sm">{category.blurb}</p>
                {large || tall ? (
                  <ul className="relative mt-5 flex flex-wrap gap-2">
                    {tools.slice(0, large ? 6 : 3).map((tool) => (
                      <li
                        key={tool.id}
                        className="bg-card/80 border-border rounded-lg border px-2.5 py-1 text-xs font-semibold backdrop-blur"
                      >
                        {tool.name}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </Link>
            </Reveal>
          );
        })}
      </ul>
    </Container>
  );
}
