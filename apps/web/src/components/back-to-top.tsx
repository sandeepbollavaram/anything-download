"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/cn";

/** Appears once the page has scrolled past the first screen (IntersectionObserver, no scroll listener). */
export function BackToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const sentinel = document.getElementById("fold-sentinel");
    if (!sentinel || typeof IntersectionObserver === "undefined") {
      return;
    }
    const io = new IntersectionObserver(([entry]) =>
      setVisible(!entry.isIntersecting && entry.boundingClientRect.top < 0),
    );
    io.observe(sentinel);
    return () => io.disconnect();
  }, []);

  return (
    <button
      type="button"
      aria-label="Back to top"
      tabIndex={visible ? 0 : -1}
      aria-hidden={!visible}
      onClick={() => {
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
        document.getElementById("main")?.focus({ preventScroll: true });
      }}
      className={cn(
        "surface-raised text-foreground hover:text-accent fixed bottom-5 right-5 z-30 grid size-12 cursor-pointer place-items-center rounded-full transition-[opacity,transform] duration-300 ease-out sm:bottom-8 sm:right-8",
        visible ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-4 opacity-0",
      )}
    >
      <ArrowUp className="size-5" />
    </button>
  );
}
