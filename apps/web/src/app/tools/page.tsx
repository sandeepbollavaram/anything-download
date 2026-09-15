import { Zap } from "lucide-react";
import Link from "next/link";

import { CategoryIcon } from "@/components/category-icon";
import { Container } from "@/components/container";
import { Reveal } from "@/components/motion/reveal";
import { PageHero, SectionHeading } from "@/components/page-hero";
import { StatusPanel } from "@/components/status-panel";
import { ToolCard } from "@/components/tool-card";
import { ToolExplorer } from "@/components/tool-explorer";
import { listTools } from "@/lib/api";
import { CATEGORIES, FEATURED_TOOL_IDS, QUICK_ACTIONS } from "@/lib/categories";
import { TOOL_CATALOGUE, getCatalogueTool } from "@/lib/catalogue";
import { copy } from "@/lib/copy";
import { pageMetadata } from "@/lib/seo";

export const dynamic = "force-dynamic";

export const metadata = pageMetadata({
  title: copy.tools.heading,
  description: copy.tools.lead,
  path: "/tools",
});

export default async function ToolsPage() {
  let liveIds: Set<string> | null = null;
  let unavailable: string[] = [];
  let usedFallback = false;

  try {
    const response = await listTools({ signal: AbortSignal.timeout(4000) });
    liveIds = new Set(response.tools.map((tool) => tool.id));
    unavailable = response.tools.filter((tool) => !tool.available).map((tool) => tool.id);
  } catch {
    usedFallback = true;
  }

  // The live server is authoritative: only list tools it actually registers.
  const tools = TOOL_CATALOGUE.filter((tool) => !liveIds || liveIds.has(tool.id));
  const featured = FEATURED_TOOL_IDS.map((id) => tools.find((tool) => tool.id === id)).filter(
    (tool): tool is NonNullable<typeof tool> => Boolean(tool),
  );
  const quick = QUICK_ACTIONS.filter((action) => tools.some((tool) => tool.id === action.id));
  const categoryCount = CATEGORIES.filter((category) =>
    tools.some((tool) => tool.category === category.id),
  ).length;

  return (
    <>
      <PageHero
        eyebrow={copy.brand.tagline}
        title={copy.tools.heading}
        lead={copy.tools.lead}
        aside={
          <dl className="surface grid grid-cols-3 divide-x divide-[var(--border)] rounded-2xl text-center">
            {[
              { label: "Tools", value: tools.length },
              { label: "Categories", value: categoryCount },
              { label: "Accounts needed", value: 0 },
            ].map((stat) => (
              <div key={stat.label} className="flex flex-col-reverse px-5 py-4 sm:px-7">
                <dt className="text-muted-foreground text-xs font-semibold">{stat.label}</dt>
                <dd className="font-display text-3xl font-extrabold tabular-nums">{stat.value}</dd>
              </div>
            ))}
          </dl>
        }
      >
        {quick.length ? (
          <nav aria-label="Quick tools" className="flex flex-wrap items-center gap-2">
            <span className="text-muted-foreground mr-1 inline-flex items-center gap-1.5 text-sm font-semibold">
              <Zap className="text-accent size-4" aria-hidden="true" />
              Quick tools
            </span>
            {quick.map((action) => {
              const tool = getCatalogueTool(action.id);
              return (
                <Link
                  key={action.id}
                  href={`/tools/${action.id}`}
                  className="bg-card border-border hover:border-border-strong shadow-xs group inline-flex min-h-10 items-center gap-2 rounded-full border py-1 pl-1.5 pr-3.5 text-sm font-semibold transition-[transform,border-color,box-shadow] duration-200 hover:-translate-y-0.5 hover:shadow-sm"
                >
                  {tool ? (
                    <CategoryIcon
                      category={tool.category}
                      size="sm"
                      className="size-7 rounded-full [&_svg]:size-3.5"
                    />
                  ) : null}
                  {action.label}
                </Link>
              );
            })}
          </nav>
        ) : null}
      </PageHero>

      <Container className="space-y-20 pt-6">
        {usedFallback ? (
          <StatusPanel
            role="status"
            error={{
              code: "CATALOGUE_FALLBACK",
              message: copy.tools.fallbackNote,
              retryable: false,
            }}
          />
        ) : null}

        {featured.length ? (
          <section aria-labelledby="featured-heading" className="space-y-8">
            <SectionHeading
              id="featured-heading"
              eyebrow="Featured"
              title="Start with the favourites"
              lead="The tools people reach for most."
            />
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {featured.map((tool, index) => (
                <Reveal as="li" key={tool.id} index={index}>
                  <ToolCard
                    tool={tool}
                    featured
                    unavailable={unavailable.includes(tool.id)}
                    catalogueOnly={usedFallback}
                  />
                </Reveal>
              ))}
            </ul>
          </section>
        ) : null}

        <section aria-labelledby="all-tools-heading" className="space-y-8">
          <SectionHeading
            id="all-tools-heading"
            eyebrow="Explore"
            title="Every tool"
            lead="Filter by category or search by format and action. Press / to search."
          />
          <ToolExplorer
            tools={tools}
            unavailable={unavailable}
            catalogueOnly={usedFallback}
            syncHash
            idPrefix="catalogue"
            headingLevel="h3"
          />
        </section>
      </Container>
    </>
  );
}
