"use client";

import { ArrowRight, Check, Download, Link2, Pause, Play, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { CategoryIcon } from "@/components/category-icon";
import { Container } from "@/components/container";
import { useMotionAllowed } from "@/components/motion/motion-toggle";
import { SectionHeading } from "@/components/page-hero";
import { cn } from "@/lib/cn";
import { copy } from "@/lib/copy";

const STEPS = ["Link", "Analysis", "Capabilities", "Processing", "Result"] as const;
const STEP_MS = 2600;

/**
 * An illustrated walkthrough, clearly labelled as an example. It plays only while visible,
 * can be paused, and stays still under reduced motion (all steps remain reachable by click).
 */
export function ProductDemo() {
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [inView, setInView] = useState(false);
  const motionAllowed = useMotionAllowed();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), {
      threshold: 0.35,
    });
    io.observe(node);
    return () => io.disconnect();
  }, []);

  const running = playing && inView && motionAllowed;

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setStep((value) => (value + 1) % STEPS.length), STEP_MS);
    return () => window.clearInterval(timer);
  }, [running]);

  return (
    <section aria-labelledby="demo-heading" className="bg-background-alt/70 border-border border-y">
      <Container className="py-16 sm:py-24">
        <SectionHeading
          id="demo-heading"
          eyebrow={copy.home.demoEyebrow}
          title={copy.home.demoTitle}
          lead={copy.home.demoLead}
        >
          {motionAllowed ? (
            <button
              type="button"
              onClick={() => setPlaying((value) => !value)}
              aria-pressed={!playing}
              className="bg-card border-border hover:border-border-strong shadow-xs inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-full border px-4 text-sm font-semibold"
            >
              {playing ? (
                <Pause className="size-4" aria-hidden="true" />
              ) : (
                <Play className="size-4" aria-hidden="true" />
              )}
              {playing ? "Pause demo" : "Play demo"}
            </button>
          ) : null}
        </SectionHeading>

        <div ref={ref} className="mt-12 grid gap-6 lg:grid-cols-[16rem_minmax(0,1fr)] xl:gap-10">
          <ol className="scrollbar-none -mx-4 flex gap-2 overflow-x-auto px-4 lg:mx-0 lg:flex-col lg:overflow-visible lg:px-0">
            {STEPS.map((label, index) => {
              const state = index < step ? "done" : index === step ? "active" : "pending";
              return (
                <li key={label} className="shrink-0">
                  <button
                    type="button"
                    onClick={() => {
                      setStep(index);
                      setPlaying(false);
                    }}
                    aria-current={index === step ? "step" : undefined}
                    className={cn(
                      "relative flex min-h-11 w-full cursor-pointer items-center gap-3 overflow-hidden rounded-xl px-3 py-2 text-left text-sm font-semibold transition-colors",
                      state === "active"
                        ? "bg-card text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground",
                    )}
                  >
                    <span
                      aria-hidden="true"
                      className={cn(
                        "grid size-6 shrink-0 place-items-center rounded-full text-xs transition-colors",
                        state === "done" && "bg-accent text-accent-foreground",
                        state === "active" && "bg-accent-soft text-accent",
                        state === "pending" && "bg-muted",
                      )}
                    >
                      {state === "done" ? (
                        <Check className="size-3.5" strokeWidth={3} />
                      ) : (
                        index + 1
                      )}
                    </span>
                    {label}
                    {state === "active" && running ? (
                      <span
                        key={`bar-${step}`}
                        aria-hidden="true"
                        className="bg-progress-gradient absolute inset-x-0 bottom-0 h-0.5 origin-left"
                        style={{ animation: `ad-scroll-progress ${STEP_MS}ms linear both` }}
                      />
                    ) : null}
                  </button>
                </li>
              );
            })}
          </ol>

          <figure className="surface-raised relative overflow-hidden rounded-3xl">
            <div className="border-border bg-background-alt/60 flex items-center justify-between gap-3 border-b px-5 py-3">
              <span aria-hidden="true" className="flex gap-1.5">
                <span className="bg-border-strong size-2.5 rounded-full" />
                <span className="bg-border-strong size-2.5 rounded-full" />
                <span className="bg-accent size-2.5 rounded-full" />
              </span>
              <figcaption className="text-muted-foreground text-xs font-semibold">
                Illustration, not a live job
              </figcaption>
            </div>
            <div className="relative flex min-h-[24rem] items-center p-5 sm:p-8" aria-live="off">
              <div aria-hidden="true" className="bg-grid absolute inset-0 opacity-50" />
              <div key={step} className="relative w-full" aria-hidden="true">
                {step === 0 ? <DemoLink /> : null}
                {step === 1 ? <DemoAnalysis /> : null}
                {step === 2 ? <DemoCapabilities /> : null}
                {step === 3 ? <DemoProcessing animate={running} /> : null}
                {step === 4 ? <DemoResult /> : null}
              </div>
              <p className="sr-only">
                Step {step + 1} of {STEPS.length}: {STEPS[step]}.
              </p>
            </div>
          </figure>
        </div>
      </Container>
    </section>
  );
}

function UrlBar({ active = false }: { active?: boolean }) {
  return (
    <div
      className={cn(
        "bg-card flex items-center gap-3 rounded-2xl border p-2 pl-4",
        active ? "border-accent ring-accent/15 ring-4" : "border-border",
      )}
    >
      <Link2 className="text-accent size-5 shrink-0" />
      <span className="min-w-0 flex-1 truncate font-mono text-sm">
        https://example.com/talk.mp4
      </span>
      <span className="bg-brand-gradient text-accent-foreground hidden rounded-xl px-4 py-2 text-sm font-bold sm:inline">
        Analyze
      </span>
    </div>
  );
}

function DemoLink() {
  return (
    <div className="animate-fade-up mx-auto max-w-2xl space-y-4">
      <p className="font-display text-2xl font-bold">Paste a public link</p>
      <UrlBar active />
      <p className="text-muted-foreground text-sm">Nothing is sent until you press Analyze.</p>
    </div>
  );
}

function DemoAnalysis() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <UrlBar />
      <div className="bg-card border-border animate-scale-in relative overflow-hidden rounded-2xl border p-4">
        <span className="scan-line via-accent/10 absolute inset-y-0 left-0 w-full bg-gradient-to-r from-transparent to-transparent" />
        <div className="relative flex items-center gap-3">
          <span className="bg-accent-soft text-accent grid size-10 place-items-center rounded-xl">
            <span className="animate-spin-slow inline-block size-4 rounded-full border-2 border-current border-r-transparent" />
          </span>
          <div>
            <p className="font-semibold">Analyzing example.com</p>
            <p className="text-muted-foreground text-sm">
              Asking the source what it publicly offers…
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

function DemoCapabilities() {
  const tools = ["Video to MP3", "Video compressor", "Video to GIF", "Video thumbnail"];
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <div className="bg-card border-border animate-scale-in flex gap-4 rounded-2xl border p-4">
        <span className="bg-muted grid aspect-video w-28 shrink-0 place-items-center rounded-lg">
          <CategoryIcon category="video" size="sm" />
        </span>
        <div className="min-w-0">
          <p className="text-muted-foreground text-xs">Detected example.com</p>
          <p className="font-display font-bold">Conference talk</p>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            {["Video", "4:12", "1920×1080", "48 MB"].map((item, index) => (
              <span
                key={item}
                className="bg-muted animate-fade-up rounded-md px-2 py-0.5 font-semibold"
                style={{ ["--i" as string]: index + 2 }}
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
      <p className="text-muted-foreground flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide">
        <Sparkles className="text-accent size-3.5" /> Tools the server offered
      </p>
      <div className="grid gap-2 sm:grid-cols-2">
        {tools.map((tool, index) => (
          <div
            key={tool}
            className={cn(
              "animate-fade-up flex items-center gap-3 rounded-xl border p-3 text-sm font-semibold",
              index === 0 ? "border-accent bg-selected-gradient" : "bg-card border-border",
            )}
            style={{ ["--i" as string]: index + 4 }}
          >
            <CategoryIcon category="video" size="sm" />
            {tool}
          </div>
        ))}
      </div>
    </div>
  );
}

function DemoProcessing({ animate }: { animate: boolean }) {
  return (
    <div className="mx-auto grid max-w-3xl items-center gap-6 sm:grid-cols-[1fr_auto]">
      <div className="space-y-4">
        <p className="font-display text-2xl font-bold">Converting</p>
        <div className="bg-muted h-2.5 overflow-hidden rounded-full">
          <div
            className="bg-progress-gradient h-full w-2/3 origin-left rounded-full"
            style={
              animate
                ? { animation: `ad-scroll-progress ${STEP_MS}ms var(--ad-ease-out) both` }
                : undefined
            }
          />
        </div>
        {[
          { label: "Queued", done: true },
          { label: "Fetching the source", done: true },
          { label: "Converting", active: true },
          { label: "Ready to download" },
        ].map((item, index) => (
          <div
            key={item.label}
            className="animate-fade-up flex items-center gap-3 text-sm"
            style={{ ["--i" as string]: index }}
          >
            <span
              className={cn(
                "grid size-6 place-items-center rounded-full",
                item.done && "bg-accent text-accent-foreground",
                item.active && "bg-accent-soft text-accent",
                !item.done && !item.active && "bg-card border",
              )}
            >
              {item.done ? <Check className="size-3.5" strokeWidth={3} /> : null}
              {item.active ? (
                <span className="animate-spin-slow inline-block size-3 rounded-full border-2 border-current border-r-transparent" />
              ) : null}
            </span>
            <span
              className={cn("font-semibold", !item.done && !item.active && "text-muted-foreground")}
            >
              {item.label}
            </span>
          </div>
        ))}
      </div>
      <div className="bg-background-alt font-display flex items-center gap-2 rounded-2xl p-5 text-sm font-bold">
        <span className="bg-card shadow-xs rounded-lg px-2 py-1">MP4</span>
        <ArrowRight className="text-accent size-4" />
        <span className="bg-accent-soft text-accent-soft-foreground rounded-lg px-2 py-1">MP3</span>
      </div>
    </div>
  );
}

function DemoResult() {
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div className="bg-card border-border animate-scale-in flex items-center gap-4 rounded-2xl border p-5 shadow-md">
        <span className="bg-success-soft text-success burst relative grid size-14 place-items-center rounded-full">
          <svg viewBox="0 0 24 24" className="size-7" fill="none">
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
          <p className="text-success text-sm font-bold">Ready</p>
          <p className="font-display truncate text-xl font-extrabold">talk.mp3</p>
          <p className="text-muted-foreground text-sm">
            6.2 MB · MP3 · deletes itself in 30 minutes
          </p>
        </div>
      </div>
      <div className="animate-fade-up flex flex-wrap gap-3 [--ad-delay:200ms]">
        <span className="bg-brand-gradient text-accent-foreground inline-flex items-center gap-2 rounded-xl px-6 py-3.5 font-bold shadow-sm">
          <Download className="size-4" />
          Download
        </span>
        <span className="bg-card border-border-strong inline-flex items-center rounded-xl border px-5 py-3.5 font-bold">
          Process another
        </span>
      </div>
    </div>
  );
}
