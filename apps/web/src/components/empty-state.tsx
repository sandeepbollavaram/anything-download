import type { LucideIcon } from "lucide-react";

import { Container } from "@/components/container";

/** Full-page state for 404, offline and unexpected errors. */
export function EmptyState({
  icon: Icon,
  code,
  title,
  lead,
  children,
}: {
  icon: LucideIcon;
  code?: string;
  title: string;
  lead?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="relative isolate -mt-[4.25rem] overflow-hidden pt-[4.25rem]">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="bg-grid absolute inset-0" />
        <div className="glow-accent animate-aurora absolute left-1/2 top-0 size-[40rem] -translate-x-1/2" />
      </div>
      <Container size="narrow" className="flex flex-col items-center py-24 text-center sm:py-32">
        <span className="surface-raised animate-scale-in mb-8 grid size-20 place-items-center rounded-3xl">
          <Icon
            className="text-accent animate-drift size-9 [--ad-drift-dur:4s] [--ad-rot:-6deg]"
            aria-hidden="true"
          />
        </span>
        {code ? (
          <p className="animate-fade-up text-gradient font-display text-sm font-extrabold uppercase tracking-[0.3em]">
            {code}
          </p>
        ) : null}
        <h1 className="animate-fade-up font-display mt-3 text-4xl font-extrabold [--ad-delay:60ms] sm:text-5xl">
          {title}
        </h1>
        {lead ? (
          <p className="animate-fade-up text-muted-foreground mt-4 max-w-md text-lg [--ad-delay:120ms]">
            {lead}
          </p>
        ) : null}
        <div className="animate-fade-up mt-8 flex flex-wrap justify-center gap-3 [--ad-delay:180ms]">
          {children}
        </div>
      </Container>
    </div>
  );
}
