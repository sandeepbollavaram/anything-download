import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { CategoryIcon } from "@/components/category-icon";
import { Container } from "@/components/container";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "@/components/page-hero";
import { categoryMeta, QUICK_ACTIONS } from "@/lib/categories";
import { getCatalogueTool } from "@/lib/catalogue";
import { copy } from "@/lib/copy";

export function QuickActions() {
  return (
    <Container
      as="section"
      aria-labelledby="popular-tools-heading"
      className="pb-16 pt-6 sm:pb-20 sm:pt-10"
    >
      <SectionHeading
        id="popular-tools-heading"
        eyebrow={copy.home.quickEyebrow}
        title={copy.home.popularHeading}
        lead={copy.home.popularLead}
      >
        <Link
          href="/tools"
          className="text-link group inline-flex min-h-11 items-center gap-2 font-semibold"
        >
          <span className="underline-grow">{copy.home.allTools}</span>
          <ArrowRight
            className="size-4 transition-transform group-hover:translate-x-0.5"
            aria-hidden="true"
          />
        </Link>
      </SectionHeading>

      <ul className="scrollbar-none -mx-4 mt-10 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-2 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 lg:grid-cols-4">
        {QUICK_ACTIONS.map((action, index) => {
          const tool = getCatalogueTool(action.id);
          if (!tool) return null;
          return (
            <Reveal
              as="li"
              key={action.id}
              index={index}
              className="w-[15rem] shrink-0 snap-start sm:w-auto"
            >
              <Link
                href={`/tools/${tool.id}`}
                style={{ ["--hue" as string]: categoryMeta(tool.category).hue }}
                className="lift surface group flex h-full min-h-20 items-center gap-4 rounded-2xl p-4"
              >
                <CategoryIcon
                  category={tool.category}
                  className="group-hover:-rotate-6 group-hover:scale-110"
                />
                <span className="min-w-0 flex-1">
                  <span className="font-display block font-bold">{action.label}</span>
                  <span className="text-muted-foreground block truncate text-sm">{tool.name}</span>
                </span>
                <ArrowRight
                  className="text-muted-foreground size-4 shrink-0 -translate-x-1 opacity-0 transition-[transform,opacity,color] duration-300 group-hover:translate-x-0 group-hover:text-[color:var(--hue)] group-hover:opacity-100 group-focus-visible:opacity-100"
                  aria-hidden="true"
                />
              </Link>
            </Reveal>
          );
        })}
      </ul>
    </Container>
  );
}
