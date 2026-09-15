import { Container } from "@/components/container";
import { cn } from "@/lib/cn";

/** Shared inner-page header band: eyebrow, title, lead, optional right-side content. */
export function PageHero({
  eyebrow,
  title,
  lead,
  children,
  aside,
  className,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  lead?: React.ReactNode;
  children?: React.ReactNode;
  aside?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("relative isolate -mt-[4.25rem] overflow-hidden pt-[4.25rem]", className)}>
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="bg-grid absolute inset-0" />
        <div className="glow-accent animate-aurora absolute -left-40 -top-48 size-[42rem]" />
        <div className="glow-cyan animate-aurora absolute -right-40 -top-24 size-[34rem] [animation-delay:-9s]" />
      </div>
      <Container className="grid items-center gap-8 pb-10 pt-10 sm:pt-14 lg:grid-cols-[minmax(0,1fr)_auto] lg:pb-12">
        <div className="max-w-3xl space-y-4">
          {eyebrow ? (
            <div className="animate-fade-up text-muted-foreground text-xs font-bold uppercase tracking-[0.18em]">
              {eyebrow}
            </div>
          ) : null}
          <h1 className="animate-fade-up font-display text-4xl font-extrabold leading-[1.05] [--ad-delay:60ms] sm:text-5xl lg:text-6xl">
            {title}
          </h1>
          {lead ? (
            <p className="animate-fade-up text-muted-foreground max-w-2xl text-lg [--ad-delay:120ms]">
              {lead}
            </p>
          ) : null}
          {children ? <div className="animate-fade-up [--ad-delay:180ms]">{children}</div> : null}
        </div>
        {aside ? <div className="animate-fade-up [--ad-delay:200ms]">{aside}</div> : null}
      </Container>
    </div>
  );
}

/** Section heading used across pages. */
export function SectionHeading({
  id,
  eyebrow,
  title,
  lead,
  className,
  align = "left",
  tone = "default",
  as: Heading = "h2",
  children,
}: {
  id?: string;
  eyebrow?: string;
  title: React.ReactNode;
  lead?: React.ReactNode;
  className?: string;
  align?: "left" | "center";
  tone?: "default" | "band";
  as?: "h1" | "h2";
  children?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-5 md:flex-row md:items-end md:justify-between",
        align === "center" && "items-center text-center md:flex-col md:items-center",
        className,
      )}
    >
      <div className={cn("max-w-2xl space-y-3", align === "center" && "mx-auto")}>
        {eyebrow ? (
          <p
            className={cn(
              "inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em]",
              tone === "band" ? "text-band-link" : "text-accent",
            )}
          >
            <span aria-hidden="true" className="h-px w-6 bg-current" />
            {eyebrow}
          </p>
        ) : null}
        <Heading
          id={id}
          className="font-display text-3xl font-extrabold leading-[1.1] sm:text-4xl lg:text-5xl"
        >
          {title}
        </Heading>
        {lead ? (
          <p
            className={cn(
              "text-base sm:text-lg",
              tone === "band" ? "text-band-muted" : "text-muted-foreground",
            )}
          >
            {lead}
          </p>
        ) : null}
      </div>
      {children}
    </div>
  );
}
