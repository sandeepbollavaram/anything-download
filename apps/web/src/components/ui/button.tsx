import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/cn";

/*
 * One primary action per view uses `default` (brand gradient). Everything else is quieter:
 * `secondary` (tinted), `outline` (surface), `ghost` and `link`. All variants press in
 * slightly on activation; icons nudge on hover via the `group` class.
 */
const buttonVariants = cva(
  "press group/button relative inline-flex cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-xl font-display text-sm font-bold disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-brand-gradient text-accent-foreground shadow-sm hover:shadow-glow hover:[background-image:var(--ad-grad-brand-hover)]",
        secondary: "bg-accent-soft text-accent-soft-foreground hover:bg-accent-soft/80",
        outline:
          "border border-border-strong bg-card text-foreground shadow-xs hover:border-input hover:bg-muted",
        ghost: "text-foreground hover:bg-muted",
        destructive: "bg-destructive text-destructive-foreground shadow-xs hover:opacity-90",
        link: "text-link underline-offset-4 hover:underline",
      },
      size: {
        default: "min-h-11 px-5 py-2",
        sm: "min-h-10 px-3.5 text-sm",
        lg: "min-h-12 px-6 text-base",
        xl: "min-h-14 px-7 text-base",
        icon: "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export type ButtonProps = React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  };

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
