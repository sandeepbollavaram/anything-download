"use client";

import { Check, Download, Link2, MousePointerClick, Sparkles, UploadCloud } from "lucide-react";
import { useState } from "react";

import { CategoryIcon } from "@/components/category-icon";
import { Container } from "@/components/container";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "@/components/page-hero";
import { cn } from "@/lib/cn";
import { copy } from "@/lib/copy";

const ICONS = [UploadCloud, MousePointerClick, Download];

export function HowItWorks() {
  const [active, setActive] = useState(0);
  const steps = copy.home.steps;

  function onKeyDown(event: React.KeyboardEvent) {
    let next = active;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") next = (active + 1) % steps.length;
    else if (event.key === "ArrowUp" || event.key === "ArrowLeft")
      next = (active - 1 + steps.length) % steps.length;
    else return;
    event.preventDefault();
    setActive(next);
    document.getElementById(`step-tab-${next}`)?.focus();
  }

  return (
    <section aria-labelledby="how-heading" className="bg-background-alt/70 border-border border-y">
      <Container className="py-16 sm:py-24">
        <SectionHeading
          id="how-heading"
          eyebrow={copy.home.stepsEyebrow}
          title={copy.home.stepsTitle}
          lead={copy.home.stepsLead}
        />
        <div className="mt-12 grid items-center gap-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-16">
          <div
            role="tablist"
            aria-label="Steps"
            aria-orientation="vertical"
            onKeyDown={onKeyDown}
            className="space-y-3"
          >
            {steps.map((step, index) => {
              const Icon = ICONS[index];
              const selected = index === active;
              return (
                <Reveal key={step.title} index={index}>
                  <button
                    id={`step-tab-${index}`}
                    type="button"
                    role="tab"
                    aria-selected={selected}
                    aria-controls="step-panel"
                    tabIndex={selected ? 0 : -1}
                    onClick={() => setActive(index)}
                    onMouseEnter={() => setActive(index)}
                    className={cn(
                      "relative flex w-full cursor-pointer gap-4 overflow-hidden rounded-2xl border p-5 text-left transition-[background-color,border-color,box-shadow] duration-300",
                      selected
                        ? "bg-card border-border shadow-md"
                        : "hover:bg-card/60 border-transparent",
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "bg-progress-gradient absolute inset-y-0 left-0 w-1 origin-top transition-transform duration-500",
                        selected ? "scale-y-100" : "scale-y-0",
                      )}
                    />
                    <span
                      className={cn(
                        "grid size-12 shrink-0 place-items-center rounded-xl transition-colors duration-300",
                        selected
                          ? "bg-brand-gradient text-accent-foreground"
                          : "bg-card text-muted-foreground border",
                      )}
                    >
                      <Icon className="size-5" aria-hidden="true" />
                    </span>
                    <span>
                      <span className="text-muted-foreground block font-mono text-xs font-bold">
                        0{index + 1}
                      </span>
                      <span className="font-display block text-xl font-bold">{step.title}</span>
                      <span className="text-muted-foreground mt-1 block">{step.body}</span>
                    </span>
                  </button>
                </Reveal>
              );
            })}
          </div>

          <div
            id="step-panel"
            role="tabpanel"
            aria-labelledby={`step-tab-${active}`}
            className="surface-raised relative min-h-80 overflow-hidden rounded-3xl p-6 sm:p-8"
          >
            <div aria-hidden="true" className="bg-grid absolute inset-0 opacity-60" />
            <div key={active} className="relative">
              {active === 0 ? <StepPaste /> : null}
              {active === 1 ? <StepPick /> : null}
              {active === 2 ? <StepDownload /> : null}
            </div>
            <p className="sr-only">{steps[active].body}</p>
          </div>
        </div>
      </Container>
    </section>
  );
}

function StepPaste() {
  return (
    <div aria-hidden="true" className="space-y-4">
      <p className="text-muted-foreground animate-fade-up text-xs font-bold uppercase tracking-[0.16em]">
        Example
      </p>
      <div className="bg-card border-accent ring-accent/15 animate-scale-in flex items-center gap-3 rounded-2xl border p-2 pl-4 ring-4">
        <Link2 className="text-accent size-5" />
        <span className="min-w-0 flex-1 truncate font-mono text-sm">
          https://example.com/lecture.mp4
          <span
            className="bg-accent ml-0.5 inline-block h-4 w-0.5 translate-y-0.5 [animation:ad-fade-out_1s_steps(2)_infinite]"
            data-motion="decorative"
          />
        </span>
        <span className="bg-brand-gradient text-accent-foreground rounded-xl px-4 py-2 text-sm font-bold">
          Analyze
        </span>
      </div>
      <div className="text-muted-foreground animate-fade-up flex items-center gap-3 text-xs font-semibold uppercase tracking-wider [--ad-delay:150ms]">
        <span className="bg-border h-px flex-1" />
        or
        <span className="bg-border h-px flex-1" />
      </div>
      <div className="border-border-strong animate-fade-up flex items-center gap-3 rounded-2xl border-2 border-dashed p-4 [--ad-delay:220ms]">
        <span className="bg-card text-accent grid size-10 place-items-center rounded-xl shadow-sm">
          <UploadCloud className="size-5" />
        </span>
        <span className="text-sm font-semibold">Drop a file here</span>
      </div>
    </div>
  );
}

function StepPick() {
  const tools = [
    { name: "Video to MP3", category: "video" as const, selected: true },
    { name: "Video compressor", category: "video" as const },
    { name: "Video to GIF", category: "video" as const },
    { name: "Video thumbnail", category: "video" as const },
  ];
  return (
    <div aria-hidden="true" className="space-y-4">
      <div className="bg-card border-border animate-scale-in flex items-center gap-3 rounded-2xl border p-3">
        <span className="bg-accent-soft text-accent grid size-9 place-items-center rounded-lg">
          <Sparkles className="size-4" />
        </span>
        <span className="text-sm">
          <span className="text-muted-foreground">Detected </span>
          <span className="font-semibold">Video · 4:12 · 1080p</span>
        </span>
      </div>
      <div className="grid gap-2.5 sm:grid-cols-2">
        {tools.map((tool, index) => (
          <div
            key={tool.name}
            className={cn(
              "animate-fade-up flex items-center gap-3 rounded-xl border p-3",
              tool.selected ? "border-accent bg-selected-gradient" : "bg-card border-border",
            )}
            style={{ ["--i" as string]: index + 2 }}
          >
            <CategoryIcon category={tool.category} size="sm" />
            <span className="flex-1 text-sm font-semibold">{tool.name}</span>
            {tool.selected ? (
              <span className="bg-accent text-accent-foreground grid size-5 place-items-center rounded-full">
                <Check className="size-3" strokeWidth={3.5} />
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

function StepDownload() {
  return (
    <div aria-hidden="true" className="space-y-5">
      <div className="bg-card border-border animate-scale-in flex items-center gap-4 rounded-2xl border p-4">
        <span className="bg-success-soft text-success burst relative grid size-12 place-items-center rounded-full">
          <svg viewBox="0 0 24 24" className="size-6" fill="none">
            <path
              d="M5 12.5l4.2 4.2L19 7"
              pathLength={1}
              stroke="currentColor"
              strokeWidth={2.6}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="draw-stroke"
            />
          </svg>
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-success text-xs font-bold">Ready</p>
          <p className="font-display truncate font-bold">lecture.mp3</p>
          <p className="text-muted-foreground text-xs">6.1 MB · MP3</p>
        </div>
      </div>
      <div className="animate-fade-up flex flex-wrap gap-3 [--ad-delay:200ms]">
        <span className="bg-brand-gradient text-accent-foreground inline-flex items-center gap-2 rounded-xl px-5 py-3 text-sm font-bold shadow-sm">
          <Download className="size-4" />
          Download
        </span>
        <span className="bg-card border-border-strong inline-flex items-center rounded-xl border px-4 py-3 text-sm font-bold">
          Process another
        </span>
      </div>
      <p className="text-muted-foreground animate-fade-up text-sm [--ad-delay:320ms]">
        Deletes itself automatically. Or delete it now.
      </p>
    </div>
  );
}
