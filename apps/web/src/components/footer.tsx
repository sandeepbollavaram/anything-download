import { Clock, EyeOff, ShieldCheck } from "lucide-react";
import Image from "next/image";
import Link from "next/link";

import { Container } from "@/components/container";
import { MotionToggle } from "@/components/motion/motion-toggle";
import { copy } from "@/lib/copy";

const groups = [
  {
    title: copy.footer.groups.product,
    links: [
      { href: "/tools", label: copy.footer.links.tools },
      { href: "/extension", label: copy.footer.links.extension },
      { href: "/about", label: copy.footer.links.about },
      { href: "/contact", label: copy.footer.links.contact },
    ],
  },
  {
    title: copy.footer.groups.legal,
    links: [
      { href: "/privacy", label: copy.footer.links.privacy },
      { href: "/terms", label: copy.footer.links.terms },
      { href: "/copyright", label: copy.footer.links.copyright },
      { href: "/security", label: copy.footer.links.security },
    ],
  },
];

const PROMISES = [
  { icon: EyeOff, label: "No tracking" },
  { icon: ShieldCheck, label: "No account" },
  { icon: Clock, label: "Auto-delete" },
];

export function Footer() {
  return (
    <footer className="bg-band text-band-foreground relative mt-24 overflow-hidden">
      {/* A soft wave edge: static SVG, no animation cost. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 1440 40"
        preserveAspectRatio="none"
        className="text-background absolute inset-x-0 top-0 z-10 h-6 w-full sm:h-8"
      >
        <path d="M0 0h1440v8c-240 30-480 30-720 12S240-2 0 20z" fill="currentColor" />
      </svg>
      <span
        aria-hidden="true"
        className="glow-accent pointer-events-none absolute -right-40 top-0 size-[36rem] opacity-60"
      />
      <Container className="relative grid gap-12 pb-12 pt-20 md:grid-cols-[1.5fr_1fr_1fr]">
        <div className="space-y-5">
          <p className="font-display flex items-center gap-3 text-2xl font-extrabold">
            <span className="grid place-items-center rounded-xl bg-white p-1">
              <Image src="/brand/mark-96.png" width={32} height={32} alt="" />
            </span>
            <span>
              Anything <span className="text-band-link">Download</span>
            </span>
          </p>
          <p className="text-band-muted max-w-sm">{copy.brand.honest}</p>
          <ul className="flex flex-wrap gap-2" aria-label="Our promises">
            {PROMISES.map((item) => (
              <li
                key={item.label}
                className="border-band-border text-band-foreground inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold"
              >
                <item.icon className="text-band-link size-3.5" aria-hidden="true" />
                {item.label}
              </li>
            ))}
          </ul>
        </div>
        {groups.map((group) => (
          <nav key={group.title} aria-label={group.title}>
            <h2 className="text-band-muted mb-3 text-xs font-bold uppercase tracking-[0.18em]">
              {group.title}
            </h2>
            <ul className="space-y-0.5">
              {group.links.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-band-foreground hover:text-band-link inline-flex min-h-11 items-center"
                  >
                    <span className="underline-grow">{link.label}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </Container>
      <div className="border-band-border relative border-t">
        <Container className="flex flex-wrap items-center justify-between gap-3 py-5">
          <p className="text-band-muted text-sm">
            {copy.footer.rights} {copy.brand.positioning}
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <p className="text-band-muted text-sm">{copy.brand.tagline}</p>
            <MotionToggle className="text-band-muted hover:text-band-foreground border-band-border inline-flex min-h-9 cursor-pointer items-center gap-1.5 rounded-full border px-3 text-xs font-semibold" />
          </div>
        </Container>
      </div>
    </footer>
  );
}
