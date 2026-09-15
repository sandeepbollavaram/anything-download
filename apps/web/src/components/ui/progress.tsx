import { cn } from "@/lib/cn";

/**
 * Determinate when the server (or the browser's upload) reports a real percentage; otherwise an
 * honest indeterminate shimmer with no number. Never pass an invented value.
 */
function Progress({
  value,
  label,
  detail,
  className,
  size = "md",
}: {
  value?: number | null;
  label?: string;
  detail?: string;
  className?: string;
  size?: "sm" | "md";
}) {
  const determinate = typeof value === "number" && !Number.isNaN(value);
  const clamped = determinate ? Math.min(100, Math.max(0, value)) : 0;

  return (
    <div className={cn("space-y-2", className)}>
      {label || determinate ? (
        <div className="flex items-baseline justify-between gap-3 text-sm">
          {label ? <p className="text-foreground font-medium">{label}</p> : <span />}
          {determinate ? (
            <span className="text-muted-foreground font-mono tabular-nums">
              {Math.round(clamped)}%
            </span>
          ) : null}
        </div>
      ) : null}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={determinate ? Math.round(clamped) : undefined}
        aria-valuetext={determinate ? `${Math.round(clamped)} percent` : label || "Processing"}
        aria-label={label}
        className={cn(
          "bg-muted relative w-full overflow-hidden rounded-full",
          size === "sm" ? "h-1.5" : "h-2.5",
        )}
      >
        {determinate ? (
          <div
            className="bg-progress-gradient h-full rounded-full transition-[width] duration-300 ease-out"
            style={{ width: `${clamped}%` }}
          />
        ) : (
          <div className="bg-progress-gradient shimmer-bar absolute inset-y-0 left-0 w-1/3 rounded-full" />
        )}
      </div>
      {detail ? <p className="text-muted-foreground text-xs">{detail}</p> : null}
    </div>
  );
}

export { Progress };
