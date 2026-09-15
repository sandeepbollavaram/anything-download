import { Check, Circle, X } from "lucide-react";

import { cn } from "@/lib/cn";

/** Circular spinner. Decorative unless given a label. */
export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span
      role={label ? "status" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn(
        "animate-spin-slow inline-block size-4 shrink-0 rounded-full border-2 border-current border-r-transparent",
        className,
      )}
    />
  );
}

/** Placeholder block for content whose dimensions are known. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("bg-muted relative block overflow-hidden rounded-lg", className)}
    >
      <span className="shimmer-bar absolute inset-y-0 left-0 w-1/2 bg-[linear-gradient(90deg,transparent,color-mix(in_oklab,var(--card)_70%,transparent),transparent)]" />
    </span>
  );
}

/** `waiting`: it is the person's turn (no work running). `active`: the server is working. */
export type StageState = "done" | "active" | "waiting" | "pending" | "error";

export type Stage = {
  id: string;
  label: string;
  detail?: string;
  state: StageState;
};

const STATE_TEXT: Record<StageState, string> = {
  done: "Done",
  active: "In progress",
  waiting: "Your turn",
  pending: "Not started",
  error: "Stopped",
};

/**
 * Vertical stage list. State is conveyed by icon shape and a visually hidden word, never by
 * colour alone. Only render stages that map to real application state.
 */
export function StageList({ stages, className }: { stages: Stage[]; className?: string }) {
  return (
    <ol className={cn("space-y-1", className)}>
      {stages.map((stage, index) => (
        <li key={stage.id} className="relative flex gap-3 pb-3 last:pb-0">
          {index < stages.length - 1 ? (
            <span
              aria-hidden="true"
              className={cn(
                "absolute left-[13px] top-7 h-[calc(100%-1.5rem)] w-0.5 rounded-full transition-colors duration-500",
                stage.state === "done" ? "bg-accent" : "bg-border",
              )}
            />
          ) : null}
          <StageIcon state={stage.state} />
          <div className="min-w-0 pt-0.5">
            <p
              className={cn(
                "text-sm font-semibold transition-colors",
                stage.state === "pending" ? "text-muted-foreground" : "text-foreground",
              )}
            >
              {stage.label}
              <span className="sr-only">: {STATE_TEXT[stage.state]}</span>
            </p>
            {stage.detail ? (
              <p className="text-muted-foreground animate-fade-in text-xs">{stage.detail}</p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

function StageIcon({ state }: { state: StageState }) {
  const base = "relative z-10 grid size-7 shrink-0 place-items-center rounded-full";
  if (state === "done") {
    return (
      <span aria-hidden="true" className={cn(base, "bg-accent text-accent-foreground animate-pop")}>
        <Check className="size-4" strokeWidth={3} />
      </span>
    );
  }
  if (state === "active") {
    return (
      <span aria-hidden="true" className={cn(base, "bg-accent-soft text-accent")}>
        <Spinner className="size-3.5" />
      </span>
    );
  }
  if (state === "waiting") {
    return (
      <span aria-hidden="true" className={cn(base, "bg-accent-soft ring-accent/40 ring-2")}>
        <span className="bg-accent ping-dot text-accent size-2.5 rounded-full" />
      </span>
    );
  }
  if (state === "error") {
    return (
      <span aria-hidden="true" className={cn(base, "bg-destructive-soft text-destructive")}>
        <X className="size-4" strokeWidth={3} />
      </span>
    );
  }
  return (
    <span aria-hidden="true" className={cn(base, "bg-card text-border-strong border")}>
      <Circle className="size-2.5" strokeWidth={3} />
    </span>
  );
}

/** Animated check mark drawn in on mount. */
export function SuccessMark({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "burst bg-success-soft text-success relative grid size-14 place-items-center rounded-full",
        className,
      )}
    >
      <svg viewBox="0 0 24 24" className="size-7" fill="none">
        <path
          d="M5 12.5l4.2 4.2L19 7"
          pathLength={1}
          stroke="currentColor"
          strokeWidth={2.6}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="draw-stroke"
          style={{ ["--ad-delay" as string]: "120ms" }}
        />
      </svg>
    </span>
  );
}
