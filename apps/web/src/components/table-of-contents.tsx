"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";

type Entry = { id: string; text: string };

/** Builds an "On this page" list from the article's h2s and highlights the section in view. */
export function TableOfContents({ targetId }: { targetId: string }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const root = document.getElementById(targetId);
    if (!root) return;
    const headings = Array.from(root.querySelectorAll("h2"));
    const found = headings.map((heading, index) => {
      if (!heading.id) {
        heading.id =
          heading.textContent
            ?.toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/(^-|-$)/g, "") || `section-${index}`;
      }
      return { id: heading.id, text: heading.textContent ?? "" };
    });
    const frame = window.requestAnimationFrame(() => setEntries(found));
    if (typeof IntersectionObserver === "undefined" || headings.length === 0) {
      return () => window.cancelAnimationFrame(frame);
    }
    const io = new IntersectionObserver(
      (items) => {
        const visible = items.filter((item) => item.isIntersecting);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    headings.forEach((heading) => io.observe(heading));
    return () => {
      window.cancelAnimationFrame(frame);
      io.disconnect();
    };
  }, [targetId]);

  if (entries.length < 2) {
    return <div className="hidden lg:block" />;
  }

  return (
    <nav aria-label="On this page" className="hidden lg:sticky lg:top-28 lg:block">
      <p className="text-muted-foreground mb-3 text-xs font-bold uppercase tracking-[0.16em]">
        On this page
      </p>
      <ul className="border-border space-y-0.5 border-l">
        {entries.map((entry) => (
          <li key={entry.id}>
            <a
              href={`#${entry.id}`}
              aria-current={active === entry.id ? "location" : undefined}
              className={cn(
                "-ml-px flex min-h-9 items-center border-l-2 pl-4 text-sm transition-colors duration-200",
                active === entry.id
                  ? "border-accent text-foreground font-semibold"
                  : "text-muted-foreground hover:text-foreground border-transparent",
              )}
            >
              {entry.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
