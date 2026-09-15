import { ArrowDown, FileText, Search, Shrink } from "lucide-react";

import type { ToolMetaphor } from "@/lib/categories";
import { cn } from "@/lib/cn";

/*
 * Small, decorative visual metaphors for work in progress: download → downward movement,
 * compress → shrinking, convert → morphing, extract → separation, render → scanning,
 * inspect → magnifier. They loop only while mounted (i.e. while real work is running) and
 * stop under reduced motion. The accompanying text always says what is happening.
 */
export function MetaphorVisual({
  metaphor,
  className,
}: {
  metaphor: ToolMetaphor;
  className?: string;
}) {
  return (
    <div aria-hidden="true" className={cn("relative grid size-24 place-items-center", className)}>
      <span className="glow-accent absolute inset-0 rounded-full" />
      {metaphor === "download" ? <Download /> : null}
      {metaphor === "compress" ? <Compress /> : null}
      {metaphor === "convert" ? <Convert /> : null}
      {metaphor === "extract" ? <Extract /> : null}
      {metaphor === "render" ? <Render /> : null}
      {metaphor === "inspect" ? <Inspect /> : null}
    </div>
  );
}

function Tile({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <span
      className={cn(
        "bg-card border-border relative grid place-items-center rounded-xl border shadow-sm",
        className,
      )}
    >
      {children}
    </span>
  );
}

function Download() {
  return (
    <div className="relative flex flex-col items-center">
      <ArrowDown
        className="text-accent size-7 [animation:ad-bounce-down_1.1s_var(--ad-ease-in-out)_infinite]"
        strokeWidth={2.6}
        data-motion="decorative"
      />
      <span className="bg-accent mt-1 h-1.5 w-12 rounded-full" />
    </div>
  );
}

function Compress() {
  return (
    <Tile className="size-14 [animation:ad-shrink_1.8s_var(--ad-ease-in-out)_infinite]">
      <Shrink className="text-accent size-6" strokeWidth={2.4} />
    </Tile>
  );
}

function Convert() {
  return (
    <div className="relative flex items-center gap-2">
      <Tile className="animate-drift size-10 [--ad-drift-dur:2.4s]">
        <span className="bg-muted-foreground/40 size-4 rounded-sm" />
      </Tile>
      <span className="flex gap-1">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="bg-accent bar-dance block h-3 w-1 rounded-full"
            style={{ ["--i" as string]: i }}
          />
        ))}
      </span>
      <Tile className="animate-drift size-10 [--ad-delay:1.2s] [--ad-drift-dur:2.4s]">
        <span className="bg-accent size-4 rounded-full" />
      </Tile>
    </div>
  );
}

function Extract() {
  return (
    <div className="relative h-16 w-16">
      <Tile className="animate-drift absolute inset-x-2 top-0 h-9 [--ad-drift-dur:2.2s] [--ad-rot:-4deg]" />
      <Tile className="bg-accent-soft animate-drift absolute inset-x-0 bottom-0 h-9 [--ad-delay:1.1s] [--ad-drift-dur:2.2s] [--ad-rot:3deg]" />
    </div>
  );
}

function Render() {
  return (
    <Tile className="relative h-16 w-12 overflow-hidden">
      <FileText className="text-muted-foreground size-5" />
      <span className="scan-line bg-accent/20 border-accent absolute inset-y-0 left-0 w-1/2 border-r-2" />
    </Tile>
  );
}

function Inspect() {
  return (
    <Tile className="size-14">
      <Search
        className="text-accent animate-drift size-6 [--ad-drift-dur:2s] [--ad-rot:-8deg]"
        strokeWidth={2.4}
      />
    </Tile>
  );
}
