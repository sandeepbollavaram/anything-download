"use client";

import { useSearchParams } from "next/navigation";

import { AnalyzeWidget } from "@/components/analyze-widget";
import { Container } from "@/components/container";
import { copy } from "@/lib/copy";

export function AnalyzeClient() {
  const params = useSearchParams();
  const url = params.get("url") ?? "";
  const upload = params.get("upload") ?? undefined;
  const tool = params.get("tool") ?? undefined;

  return (
    <div className="relative isolate -mt-[4.25rem] overflow-hidden pt-[4.25rem]">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[34rem]"
      >
        <div className="bg-grid absolute inset-0" />
        <div className="glow-accent animate-aurora absolute -left-40 -top-48 size-[42rem]" />
        <div className="glow-cyan animate-aurora absolute -right-40 -top-24 size-[30rem] [animation-delay:-9s]" />
      </div>
      <Container className="space-y-8 py-10 sm:py-14">
        <div className="max-w-3xl space-y-3">
          <p className="animate-fade-up text-accent text-xs font-bold uppercase tracking-[0.18em]">
            Workspace
          </p>
          <h1 className="animate-fade-up font-display text-4xl font-extrabold [--ad-delay:60ms] sm:text-5xl">
            {copy.widget.resultsHeading}
          </h1>
          <p className="animate-fade-up text-muted-foreground text-lg [--ad-delay:120ms]">
            {copy.brand.honest}
          </p>
        </div>
        <AnalyzeWidget preselectedTool={tool} initialUrl={url} initialUploadId={upload} />
      </Container>
    </div>
  );
}
