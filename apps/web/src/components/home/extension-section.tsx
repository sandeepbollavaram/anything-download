import {
  ArrowRight,
  Check,
  FileText,
  Image as ImageIcon,
  Lock,
  Music,
  Puzzle,
  Video,
} from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { Container } from "@/components/container";
import { Reveal } from "@/components/motion/reveal";
import { Button } from "@/components/ui/button";
import { copy } from "@/lib/copy";

const PERMISSIONS = ["activeTab only", "No history or cookies", "No content scripts"];

export function ExtensionSection() {
  return (
    <Container as="section" aria-labelledby="extension-heading" className="py-16 sm:py-24">
      <div className="surface-raised relative isolate grid items-center gap-10 overflow-hidden rounded-[2rem] p-6 sm:p-10 lg:grid-cols-2 lg:p-14">
        <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
          <div className="glow-accent absolute -right-20 -top-20 size-[36rem]" />
          <div className="bg-grid absolute inset-0 opacity-70" />
        </div>
        <div className="space-y-6">
          <p className="text-accent inline-flex items-center gap-2 text-xs font-bold uppercase tracking-[0.18em]">
            <Puzzle className="size-4" aria-hidden="true" />
            {copy.home.extensionEyebrow}
          </p>
          <h2
            id="extension-heading"
            className="font-display text-3xl font-extrabold leading-[1.1] sm:text-4xl lg:text-5xl"
          >
            {copy.home.extensionTitle}
          </h2>
          <p className="text-muted-foreground max-w-lg text-lg">{copy.home.extensionBody}</p>
          <ul className="flex flex-wrap gap-2" aria-label="Permissions">
            {PERMISSIONS.map((item) => (
              <li
                key={item}
                className="bg-success-soft text-success inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold"
              >
                <Check className="size-3.5" strokeWidth={3} aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap items-center gap-4">
            <Button asChild size="lg">
              <Link href="/extension">
                {copy.legal.extension.homeLink}
                <ArrowRight className="transition-transform group-hover/button:translate-x-0.5" />
              </Link>
            </Button>
            <p className="text-muted-foreground text-sm">{copy.legal.extension.homeNote}</p>
          </div>
        </div>

        <Reveal className="relative mx-auto w-full max-w-sm">
          <ExtensionPreview />
        </Reveal>
      </div>
    </Container>
  );
}

/** A faithful, static preview of the popup. Decorative: the real permissions are listed beside it. */
export function ExtensionPreview() {
  const found = [
    { icon: ImageIcon, label: "Images", count: 12, hue: "var(--cat-image)" },
    { icon: Video, label: "Videos", count: 2, hue: "var(--cat-video)" },
    { icon: Music, label: "Audio", count: 1, hue: "var(--cat-audio)" },
    { icon: FileText, label: "PDFs", count: 3, hue: "var(--cat-pdf)" },
  ];
  return (
    <figure aria-hidden="true" className="relative">
      <div className="bg-brand-gradient absolute -inset-4 -z-10 rounded-[2rem] opacity-15 blur-2xl" />
      <div className="bg-card border-border overflow-hidden rounded-2xl border shadow-lg">
        <div className="border-border flex items-center gap-2.5 border-b px-4 py-3">
          <span className="grid place-items-center rounded-lg bg-white p-0.5">
            <Image src="/brand/mark-48.png" width={22} height={22} alt="" />
          </span>
          <span className="font-display text-sm font-extrabold">
            Anything <span className="text-link">Download</span>
          </span>
        </div>
        <div className="space-y-3 p-4">
          <div className="bg-muted rounded-xl px-3 py-2">
            <p className="text-muted-foreground text-[11px]">Current page</p>
            <p className="truncate font-mono text-xs">example.com/articles/field-notes</p>
          </div>
          <span className="bg-brand-gradient text-accent-foreground flex min-h-10 items-center justify-center rounded-xl text-sm font-bold">
            Analyze this page
          </span>
          <ul className="space-y-1.5">
            {found.map((item, index) => (
              <li
                key={item.label}
                className="animate-fade-up border-border flex items-center gap-3 rounded-xl border px-3 py-2"
                style={{ ["--i" as string]: index + 2, ["--hue" as string]: item.hue }}
              >
                <span className="grid size-7 place-items-center rounded-lg text-[color:var(--hue)] [background:color-mix(in_oklab,var(--hue)_14%,transparent)]">
                  <item.icon className="size-3.5" />
                </span>
                <span className="flex-1 text-sm font-semibold">{item.label}</span>
                <span className="text-muted-foreground font-mono text-xs">{item.count}</span>
              </li>
            ))}
          </ul>
          <p className="bg-warning-soft text-warning flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-semibold">
            <Lock className="size-3.5" />
            One video needs a login, so it&apos;s skipped.
          </p>
        </div>
      </div>
    </figure>
  );
}
