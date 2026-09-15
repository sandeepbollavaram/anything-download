import * as React from "react";

import { cn } from "@/lib/cn";

const field =
  "border-input/60 bg-card text-foreground placeholder:text-muted-foreground w-full min-w-0 rounded-xl border px-4 text-base shadow-xs transition-[border-color,box-shadow] duration-200 hover:border-input focus-visible:border-accent focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/15 disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-destructive";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return <input type={type} className={cn(field, "flex min-h-12 py-2", className)} {...props} />;
}

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return <textarea className={cn(field, "flex min-h-28 py-3", className)} {...props} />;
}

function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      className={cn("text-foreground mb-2 block text-sm font-semibold", className)}
      {...props}
    />
  );
}

function NativeSelect({ className, ...props }: React.ComponentProps<"select">) {
  return (
    <select className={cn(field, "flex min-h-12 cursor-pointer py-2", className)} {...props} />
  );
}

export { Input, Label, NativeSelect, Textarea };
