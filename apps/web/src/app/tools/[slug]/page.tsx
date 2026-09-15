import { ArrowUpRight, Check, ChevronRight, X } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AnalyzeWidget } from "@/components/analyze-widget";
import { CategoryIcon } from "@/components/category-icon";
import { Container } from "@/components/container";
import { JsonLd } from "@/components/json-ld";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "@/components/page-hero";
import { ToolCard } from "@/components/tool-card";
import { categoryMeta, inputLabels } from "@/lib/categories";
import { TOOL_CATALOGUE, TOOL_IDS, getCatalogueTool } from "@/lib/catalogue";
import { copy } from "@/lib/copy";
import { toolJsonLd, toolMetadata } from "@/lib/seo";

export function generateStaticParams() {
  return TOOL_IDS.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const tool = getCatalogueTool(slug);
  if (!tool) {
    return {};
  }
  return toolMetadata(tool);
}

export default async function ToolPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const tool = getCatalogueTool(slug);
  if (!tool) {
    notFound();
  }
  const meta = categoryMeta(tool.category);
  const related = TOOL_CATALOGUE.filter(
    (item) => item.category === tool.category && item.id !== tool.id,
  ).slice(0, 4);

  const sidebar = (
    <>
      <div className="surface rounded-2xl p-5">
        <p className="text-muted-foreground mb-3 text-xs font-bold uppercase tracking-[0.16em]">
          {copy.tools.accepts}
        </p>
        <ul className="space-y-2 text-sm">
          {tool.accepts.map((item) => (
            <li key={item} className="flex gap-2.5">
              <Check
                className="text-success mt-0.5 size-4 shrink-0"
                strokeWidth={3}
                aria-hidden="true"
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>
      {related.length ? (
        <div className="surface rounded-2xl p-5">
          <p className="text-muted-foreground mb-2 text-xs font-bold uppercase tracking-[0.16em]">
            {copy.tools.related}
          </p>
          <ul>
            {related.slice(0, 3).map((item) => (
              <li key={item.id}>
                <Link
                  href={`/tools/${item.id}`}
                  className="hover:bg-muted group -mx-2 flex min-h-11 items-center gap-3 rounded-xl px-2 py-1.5 text-sm font-semibold"
                >
                  <CategoryIcon category={item.category} size="sm" />
                  <span className="flex-1">{item.name}</span>
                  <ArrowUpRight
                    className="text-muted-foreground size-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                    aria-hidden="true"
                  />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );

  return (
    <article>
      <JsonLd data={toolJsonLd(tool)} />
      <div className="relative isolate -mt-[4.25rem] overflow-hidden pt-[4.25rem]">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[36rem]"
        >
          <div className="bg-grid absolute inset-0" />
          <div
            className="animate-aurora absolute -left-40 -top-48 size-[42rem] rounded-full"
            style={{
              background: `radial-gradient(closest-side, color-mix(in oklab, ${meta.hue} 16%, transparent), transparent)`,
            }}
          />
          <div className="glow-cyan animate-aurora absolute -right-40 -top-24 size-[30rem] [animation-delay:-9s]" />
        </div>

        <Container className="pb-8 pt-8 sm:pt-12">
          <nav aria-label="Breadcrumb" className="animate-fade-up">
            <ol className="text-muted-foreground flex flex-wrap items-center gap-1 text-sm">
              <li>
                <Link
                  href="/tools"
                  className="hover:text-foreground inline-flex min-h-11 items-center font-medium"
                >
                  {copy.nav.tools}
                </Link>
              </li>
              <li aria-hidden="true">
                <ChevronRight className="size-4" />
              </li>
              <li>
                <Link
                  href={`/tools#${tool.category}`}
                  className="hover:text-foreground inline-flex min-h-11 items-center font-medium"
                >
                  {meta.label}
                </Link>
              </li>
            </ol>
          </nav>
          <header className="mt-2 flex flex-col gap-5 sm:flex-row sm:items-center">
            <CategoryIcon
              category={tool.category}
              size="lg"
              className="animate-scale-in size-16 [&_svg]:size-8"
            />
            <div className="min-w-0 space-y-2">
              <h1 className="animate-fade-up font-display text-4xl font-extrabold leading-[1.05] [--ad-delay:60ms] sm:text-5xl">
                {tool.name}
              </h1>
              <p className="animate-fade-up text-muted-foreground max-w-3xl text-lg [--ad-delay:120ms]">
                {tool.description}
              </p>
            </div>
          </header>
          <ul
            className="animate-fade-up mt-5 flex flex-wrap gap-2 [--ad-delay:180ms]"
            aria-label="Tool facts"
          >
            {[`Input: ${inputLabels(tool).join(", ")}`, ...copy.home.trust].map((item) => (
              <li
                key={item}
                className="bg-card/80 border-border inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold backdrop-blur"
              >
                <Check className="text-success size-3.5" strokeWidth={3} aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </Container>
      </div>

      <Container className="space-y-20">
        <div className="animate-fade-up [--ad-delay:220ms]">
          <AnalyzeWidget preselectedTool={tool.id} aside={sidebar} />
        </div>

        <section aria-labelledby="how-heading" className="space-y-8">
          <SectionHeading id="how-heading" eyebrow="Step by step" title={copy.tools.howItWorks} />
          <ol className="grid gap-4 md:grid-cols-3">
            {tool.howItWorks.map((step, index) => (
              <Reveal as="li" key={step} index={index} className="surface relative rounded-2xl p-6">
                <span
                  aria-hidden="true"
                  className="text-gradient font-display mb-3 block text-4xl font-extrabold"
                >
                  0{index + 1}
                </span>
                <p className="text-base">{step}</p>
              </Reveal>
            ))}
          </ol>
        </section>

        <section
          aria-labelledby="willnot-heading"
          className="grid items-start gap-8 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]"
        >
          <SectionHeading
            id="willnot-heading"
            eyebrow="Honest limits"
            title={copy.tools.willNot}
            lead="Refusing these is a feature. It keeps the service safe, legal and trustworthy."
          />
          <ul className="grid gap-3">
            {tool.willNot.map((item, index) => (
              <Reveal
                as="li"
                key={item}
                index={index}
                className="surface flex gap-4 rounded-2xl p-5"
              >
                <span
                  aria-hidden="true"
                  className="bg-destructive-soft text-destructive grid size-9 shrink-0 place-items-center rounded-xl"
                >
                  <X className="size-4" strokeWidth={3} />
                </span>
                <span className="pt-1.5">{item}</span>
              </Reveal>
            ))}
          </ul>
        </section>

        {related.length > 0 ? (
          <section aria-labelledby="related-heading" className="space-y-8">
            <SectionHeading id="related-heading" eyebrow={meta.label} title={copy.tools.related} />
            <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {related.map((item, index) => (
                <Reveal as="li" key={item.id} index={index}>
                  <ToolCard tool={item} />
                </Reveal>
              ))}
            </ul>
          </section>
        ) : null}
      </Container>
    </article>
  );
}
