"use client";

import { useEffect, useRef } from "react";

import { cn } from "@/lib/cn";

let observer: IntersectionObserver | null = null;

function getObserver() {
  if (!observer && typeof IntersectionObserver !== "undefined") {
    // One observer for the whole page; each element is revealed once, then released.
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.setAttribute("data-visible", "");
            observer?.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 },
    );
  }
  return observer;
}

type RevealProps = React.HTMLAttributes<HTMLElement> & {
  as?: "div" | "section" | "li" | "ul" | "ol" | "article" | "header";
  /** Stagger index; each step adds 70ms. */
  index?: number;
};

/** Fades and rises content into view on scroll. Visible without JS and under reduced motion. */
export function Reveal({ as: Tag = "div", index, className, style, ...props }: RevealProps) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const node = ref.current;
    const io = getObserver();
    if (!node) {
      return;
    }
    if (!io) {
      node.setAttribute("data-visible", "");
      return;
    }
    io.observe(node);
    return () => io.unobserve(node);
  }, []);

  return (
    <Tag
      ref={ref as React.Ref<never>}
      className={cn("reveal", className)}
      style={index != null ? { ...style, ["--i" as string]: index } : style}
      {...props}
    />
  );
}
