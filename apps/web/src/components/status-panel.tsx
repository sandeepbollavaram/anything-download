"use client";

import { RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import type { ErrorPayload } from "@/lib/api";
import { cn } from "@/lib/cn";
import { presentError } from "@/lib/error-presentation";

const TONES = {
  danger: "border-destructive/30 bg-destructive-soft [--tone:var(--destructive)]",
  warning: "border-warning/30 bg-warning-soft [--tone:var(--warning)]",
  neutral: "border-border bg-muted [--tone:var(--foreground)]",
} as const;

/**
 * A clear, human error surface: icon, title, the server's exact explanation, and what to do
 * next. `role="alert"` is announced once. Rate limits count down from the server's own
 * Retry-After value; the retry button unlocks when it ends.
 */
export function StatusPanel({
  error,
  onRetry,
  retryLabel = "Try again",
  className,
  children,
  role = "alert",
}: {
  error: ErrorPayload;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
  children?: React.ReactNode;
  role?: "alert" | "status";
}) {
  const presentation = presentError(error);
  const Icon = presentation.icon;
  const countdown = useCountdown(
    error.code === "RATE_LIMITED" ? error.retryAfterSeconds : undefined,
  );
  const showRetry = Boolean(onRetry && (error.retryable || error.code === "RATE_LIMITED"));
  const shake = error.code === "FILE_TOO_LARGE" || error.code === "VALIDATION_ERROR";

  return (
    <div
      role={role}
      className={cn(
        "animate-scale-in rounded-2xl border p-4 sm:p-5",
        TONES[presentation.tone],
        shake && "animate-shake",
        className,
      )}
    >
      <div className="flex gap-4">
        <span
          aria-hidden="true"
          className="bg-card shadow-xs grid size-10 shrink-0 place-items-center rounded-xl text-[color:var(--tone)]"
        >
          <Icon className="size-5" strokeWidth={2.2} />
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <p className="font-display text-foreground font-bold">{presentation.title}</p>
          {error.message && error.message !== presentation.title ? (
            <p className="text-foreground text-sm">{error.message}</p>
          ) : null}
          <p className="text-muted-foreground text-sm">{presentation.next}</p>

          {countdown != null && countdown > 0 ? (
            <CountdownBar remaining={countdown} total={error.retryAfterSeconds ?? countdown} />
          ) : null}

          {showRetry || children ? (
            <div className="flex flex-wrap items-center gap-3 pt-2">
              {showRetry ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={countdown != null && countdown > 0}
                  onClick={onRetry}
                  className="group"
                >
                  <RotateCcw className="transition-transform duration-500 group-hover:-rotate-180" />
                  {countdown != null && countdown > 0
                    ? `${retryLabel} in ${countdown}s`
                    : retryLabel}
                </Button>
              ) : null}
              {children}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function CountdownBar({ remaining, total }: { remaining: number; total: number }) {
  const percent = Math.max(0, Math.min(100, (remaining / Math.max(1, total)) * 100));
  return (
    <div className="pt-2" aria-hidden="true">
      <div className="bg-card h-1.5 w-full overflow-hidden rounded-full">
        <div
          className="h-full rounded-full bg-[color:var(--tone)] transition-[width] duration-1000 ease-linear"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}

/** Counts down from the server's Retry-After. The panel is remounted for each new error. */
function useCountdown(seconds: number | undefined) {
  const [end] = useState(() => (seconds ? Date.now() + seconds * 1000 : null));
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!end) {
      return;
    }
    const timer = window.setInterval(() => {
      const current = Date.now();
      setNow(current);
      if (current >= end) {
        window.clearInterval(timer);
      }
    }, 250);
    return () => window.clearInterval(timer);
  }, [end]);

  return end ? Math.max(0, Math.ceil((end - now) / 1000)) : null;
}
