import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold [&_svg]:size-3.5",
  {
    variants: {
      variant: {
        default: "border-transparent bg-accent-soft text-accent-soft-foreground",
        outline: "border-border bg-card text-muted-foreground",
        warning: "border-warning/30 bg-warning-soft text-warning",
        danger: "border-destructive/30 bg-destructive-soft text-destructive",
        success: "border-success/30 bg-success-soft text-success",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

function Badge({
  className,
  variant,
  ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}

export { Badge, badgeVariants };
