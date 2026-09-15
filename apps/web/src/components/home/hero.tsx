import {
  Clock,
  EyeOff,
  FileText,
  Film,
  Globe,
  Image as ImageIcon,
  Music,
  UserX,
} from "lucide-react";

import { AnalyzeWidget } from "@/components/analyze-widget";
import { Container } from "@/components/container";
import { TOOL_CATALOGUE } from "@/lib/catalogue";
import { cn } from "@/lib/cn";
import { copy } from "@/lib/copy";

const FLOATING = [
  {
    icon: Globe,
    hue: "var(--cat-web)",
    label: "HTML",
    className: "-top-9 left-12",
    rot: "-5deg",
    delay: "0s",
  },
  {
    icon: Music,
    hue: "var(--cat-audio)",
    label: "MP3",
    className: "-top-7 right-10",
    rot: "6deg",
    delay: "-2s",
  },
  {
    icon: Film,
    hue: "var(--cat-video)",
    label: "MP4",
    className: "top-[42%] -left-24",
    rot: "-7deg",
    delay: "-4s",
  },
  {
    icon: ImageIcon,
    hue: "var(--cat-image)",
    label: "WEBP",
    className: "-bottom-4 -left-10",
    rot: "5deg",
    delay: "-1s",
  },
  {
    icon: FileText,
    hue: "var(--cat-pdf)",
    label: "PDF",
    className: "-bottom-2 -right-6",
    rot: "-4deg",
    delay: "-3s",
  },
];

export function Hero() {
  const headingWords = copy.home.heading.split(" ");
  const accentWords = copy.home.headingAccent.split(" ");

  return (
    <section
      aria-labelledby="hero-heading"
      className="relative isolate -mt-[4.25rem] overflow-hidden pt-[4.25rem]"
    >
      {/* Ambient light and a faint technical grid. Decorative only. */}
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="bg-grid absolute inset-0" />
        <div className="glow-accent animate-aurora absolute -left-60 -top-60 size-[56rem]" />
        <div className="glow-cyan animate-aurora absolute -right-40 top-20 size-[44rem] [animation-delay:-9s]" />
        <div className="from-background absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t to-transparent" />
      </div>

      <Container className="grid items-center gap-12 pb-16 pt-10 sm:pt-16 lg:min-h-[min(calc(100svh-4.25rem),56rem)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1.08fr)] lg:gap-16 lg:pb-16 xl:gap-24">
        <div className="space-y-8">
          <p className="animate-fade-up bg-card/80 border-border shadow-xs inline-flex items-center gap-2.5 rounded-full border py-1.5 pl-2 pr-4 text-sm font-semibold backdrop-blur">
            <span className="bg-success-soft text-success grid size-6 place-items-center rounded-full">
              <span className="ping-dot inline-block size-2 rounded-full bg-current" />
            </span>
            {copy.home.badge}
            <span className="text-muted-foreground hidden font-medium sm:inline">
              · {copy.brand.tagline}
            </span>
          </p>

          <h1
            id="hero-heading"
            className="font-display text-[2.75rem] font-extrabold leading-[1.02] tracking-[-0.035em] sm:text-6xl xl:text-7xl 2xl:text-[5.25rem]"
          >
            {headingWords.map((word, index) => (
              <span key={`h-${index}`}>
                <span className="animate-word" style={{ ["--i" as string]: index }}>
                  {word}
                </span>{" "}
              </span>
            ))}
            <br className="hidden sm:block" />
            {accentWords.map((word, index) => (
              <span key={`a-${index}`}>
                <span
                  className="animate-word text-gradient pb-1"
                  style={{ ["--i" as string]: headingWords.length + index }}
                >
                  {word}
                </span>
                {index < accentWords.length - 1 ? " " : ""}
              </span>
            ))}
          </h1>

          <p
            className="animate-fade-up text-muted-foreground max-w-xl text-lg sm:text-xl"
            style={{ ["--ad-delay" as string]: "520ms" }}
          >
            {copy.home.lead}
          </p>

          <ul aria-label="What you can do" className="flex flex-wrap gap-2">
            {copy.home.verbs.map((verb, index) => (
              <li
                key={verb}
                className="animate-fade-up bg-card border-border shadow-xs rounded-xl border px-3.5 py-1.5 text-sm font-bold"
                style={{ ["--ad-delay" as string]: `${620 + index * 70}ms` }}
              >
                {verb}
              </li>
            ))}
          </ul>

          <dl
            className="animate-fade-up grid max-w-lg grid-cols-3 gap-4"
            style={{ ["--ad-delay" as string]: "900ms" }}
          >
            {[
              { icon: Globe, value: `${TOOL_CATALOGUE.length}`, label: "focused tools" },
              { icon: UserX, value: "0", label: "accounts needed" },
              { icon: Clock, value: "Auto", label: "file deletion" },
            ].map((stat) => (
              <div key={stat.label} className="flex flex-col-reverse gap-0.5">
                <dt className="text-muted-foreground text-xs font-medium sm:text-sm">
                  {stat.label}
                </dt>
                <dd className="font-display flex items-center gap-1.5 text-2xl font-extrabold tabular-nums">
                  {stat.value}
                </dd>
              </div>
            ))}
          </dl>
        </div>

        <div className="animate-scale-in relative [--ad-delay:250ms]">
          <div
            aria-hidden="true"
            className="bg-brand-gradient absolute -inset-6 -z-10 rounded-[2.5rem] opacity-[0.12] blur-3xl"
          />
          <div aria-hidden="true" className="hidden lg:block">
            {FLOATING.map((item, index) => (
              <span
                key={item.label}
                className={cn("animate-drift absolute z-10 hidden xl:block", item.className)}
                style={{
                  ["--ad-rot" as string]: item.rot,
                  ["--ad-delay" as string]: item.delay,
                  ["--ad-drift-dur" as string]: `${8 + index}s`,
                }}
              >
                <span
                  className="surface-raised animate-scale-in flex items-center gap-2 rounded-2xl py-2 pl-2 pr-3"
                  style={{
                    ["--ad-delay" as string]: `${700 + index * 90}ms`,
                    ["--hue" as string]: item.hue,
                  }}
                >
                  <span className="grid size-8 place-items-center rounded-xl text-[color:var(--hue)] [background:color-mix(in_oklab,var(--hue)_14%,transparent)]">
                    <item.icon className="size-4" strokeWidth={2.4} />
                  </span>
                  <span className="font-mono text-xs font-bold">{item.label}</span>
                </span>
              </span>
            ))}
          </div>
          <AnalyzeWidget redirectOnSubmit layout="hero" />
          <p className="text-muted-foreground mt-4 flex items-center justify-center gap-2 text-xs">
            <EyeOff className="size-3.5" aria-hidden="true" />
            Only public content, or files you have the right to use.
          </p>
        </div>
      </Container>
    </section>
  );
}
