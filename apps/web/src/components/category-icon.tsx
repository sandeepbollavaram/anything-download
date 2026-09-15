import { categoryMeta } from "@/lib/categories";
import type { ToolCategory } from "@/lib/catalogue";
import { cn } from "@/lib/cn";

/** Category icon tile in the category's identity hue. Decorative; the name is always shown. */
export function CategoryIcon({
  category,
  className,
  size = "md",
}: {
  category: ToolCategory;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const meta = categoryMeta(category);
  const Icon = meta.icon;
  return (
    <span
      aria-hidden="true"
      style={{ ["--hue" as string]: meta.hue }}
      className={cn(
        "inline-grid shrink-0 place-items-center rounded-xl text-[color:var(--hue)] transition-transform duration-300 [background:color-mix(in_oklab,var(--hue)_12%,transparent)]",
        size === "sm" && "size-8 rounded-lg [&_svg]:size-4",
        size === "md" && "size-11 [&_svg]:size-5",
        size === "lg" && "size-14 rounded-2xl [&_svg]:size-7",
        className,
      )}
    >
      <Icon strokeWidth={2.2} />
    </span>
  );
}
