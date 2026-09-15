import type { ReactNode } from "react";

import { Container } from "@/components/container";
import { PageHero } from "@/components/page-hero";
import { TableOfContents } from "@/components/table-of-contents";
import { copy } from "@/lib/copy";

export function LegalPage({
  title,
  lead,
  children,
  heroAside,
}: {
  title: string;
  lead?: string;
  children: ReactNode;
  heroAside?: ReactNode;
}) {
  return (
    <>
      <PageHero eyebrow={copy.brand.name} title={title} lead={lead} aside={heroAside} />
      <Container className="grid items-start gap-10 pt-4 lg:grid-cols-[14rem_minmax(0,1fr)] xl:grid-cols-[16rem_minmax(0,48rem)] xl:gap-20">
        <TableOfContents targetId="legal-body" />
        <article
          id="legal-body"
          className="surface animate-fade-up [&_a]:text-link [&_code]:bg-muted [&_h2]:font-display [&_li]:marker:text-accent [&_strong]:text-foreground space-y-4 rounded-3xl p-6 text-base leading-7 [--ad-delay:200ms] sm:p-10 sm:text-lg sm:leading-8 [&_a]:font-semibold [&_a]:underline [&_a]:underline-offset-4 [&_code]:rounded [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:text-sm [&_h2:first-child]:pt-0 [&_h2]:scroll-mt-28 [&_h2]:pt-6 [&_h2]:text-2xl [&_h2]:font-extrabold [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6"
        >
          {children}
        </article>
      </Container>
    </>
  );
}
