import { Clock, EyeOff, Scale, ShieldCheck, UserX } from "lucide-react";

import { Container } from "@/components/container";
import { Reveal } from "@/components/motion/reveal";
import { SectionHeading } from "@/components/page-hero";
import { copy } from "@/lib/copy";

const ICONS = [EyeOff, UserX, Clock, Scale, ShieldCheck];

export function Trust() {
  return (
    <section
      aria-labelledby="why-heading"
      className="bg-band text-band-foreground relative isolate overflow-hidden"
    >
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="glow-accent animate-aurora absolute -left-40 top-0 size-[40rem] opacity-80" />
        <div className="absolute inset-0 [background-image:linear-gradient(rgb(238_242_251/0.04)_1px,transparent_1px),linear-gradient(90deg,rgb(238_242_251/0.04)_1px,transparent_1px)] [background-size:48px_48px] [mask-image:radial-gradient(ellipse_60%_60%_at_30%_40%,#000_30%,transparent_100%)]" />
      </div>
      <Container className="grid gap-14 py-20 sm:py-28 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:gap-20">
        <div className="space-y-8">
          <SectionHeading
            id="why-heading"
            tone="band"
            eyebrow={copy.home.whyEyebrow}
            title={copy.home.whyTitle}
            lead={copy.home.whyLead}
          />
          <Reveal className="border-band-border flex items-center gap-5 rounded-3xl border bg-white/[0.03] p-6">
            <DeleteRing />
            <div>
              <p className="font-display text-lg font-bold">Every file has an expiry.</p>
              <p className="text-band-muted text-sm">
                Results are removed automatically after a short window. You can also delete them
                yourself the moment you&apos;re done.
              </p>
            </div>
          </Reveal>
        </div>
        <ul className="grid gap-4 sm:grid-cols-2">
          {copy.home.why.map((item, index) => {
            const Icon = ICONS[index];
            return (
              <Reveal
                as="li"
                key={item.title}
                index={index}
                className={
                  index === copy.home.why.length - 1
                    ? "border-band-border group rounded-2xl border bg-white/[0.03] p-6 transition-colors duration-300 hover:bg-white/[0.06] sm:col-span-2"
                    : "border-band-border group rounded-2xl border bg-white/[0.03] p-6 transition-colors duration-300 hover:bg-white/[0.06]"
                }
              >
                <span
                  aria-hidden="true"
                  className="text-band-link relative mb-4 grid size-11 place-items-center rounded-xl bg-white/[0.06] transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-110"
                >
                  <Icon className="size-5" strokeWidth={2.2} />
                </span>
                <h3 className="font-display text-lg font-bold">{item.title}</h3>
                <p className="text-band-muted mt-1">{item.body}</p>
              </Reveal>
            );
          })}
        </ul>
      </Container>
    </section>
  );
}

/** A ring that draws closed when it scrolls into view: "this file has a limited life". */
function DeleteRing() {
  return (
    <span aria-hidden="true" className="relative grid size-16 shrink-0 place-items-center">
      <svg viewBox="0 0 64 64" className="absolute inset-0 -rotate-90">
        <circle
          cx="32"
          cy="32"
          r="26"
          fill="none"
          stroke="rgb(238 242 251 / 0.1)"
          strokeWidth="6"
        />
        <circle
          cx="32"
          cy="32"
          r="26"
          fill="none"
          stroke="var(--band-link)"
          strokeWidth="6"
          strokeLinecap="round"
          pathLength={1}
          className="draw-stroke"
          style={{ ["--ad-delay" as string]: "300ms" }}
        />
      </svg>
      <Clock className="text-band-link size-6" />
    </span>
  );
}
