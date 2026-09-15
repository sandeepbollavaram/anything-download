import * as React from "react";

import { cn } from "@/lib/cn";

/*
 * Surfaces: `plain` (flat, bordered), `default` (bordered with a soft shadow), `raised`
 * (primary workspace panels), `lift` (interactive tiles that rise on hover/focus).
 */
const surfaces = {
  plain: "border border-border bg-card",
  default: "surface",
  raised: "surface-raised",
  lift: "lift surface",
} as const;

function Card({
  className,
  surface = "default",
  ...props
}: React.ComponentProps<"div"> & { surface?: keyof typeof surfaces }) {
  return (
    <div
      className={cn("text-card-foreground rounded-2xl p-5 sm:p-6", surfaces[surface], className)}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("mb-4 space-y-1", className)} {...props} />;
}

function CardTitle({ className, ...props }: React.ComponentProps<"h2">) {
  return <h2 className={cn("font-display text-lg font-bold", className)} {...props} />;
}

function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return <p className={cn("text-muted-foreground text-sm", className)} {...props} />;
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("space-y-4", className)} {...props} />;
}

export { Card, CardContent, CardDescription, CardHeader, CardTitle };
