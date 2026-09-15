import { cn } from "@/lib/cn";

/*
 * Layout widths. `wide` is the default page frame (~1440px of content on large screens) with
 * padding that grows with the viewport: 16px → 24 → 40 → 56 → 72 → 88. `default` suits
 * reading-heavy sections, `narrow` long-form prose.
 */
const sizes = {
  narrow: "max-w-3xl",
  default: "max-w-6xl",
  wide: "max-w-[1600px]",
} as const;

export function Container({
  size = "wide",
  className,
  as: Tag = "div",
  ...props
}: React.ComponentProps<"div"> & {
  size?: keyof typeof sizes;
  as?: "div" | "section" | "header" | "footer" | "article";
}) {
  return (
    <Tag
      className={cn(
        "mx-auto w-full px-4 sm:px-6 md:px-10 lg:px-14 xl:px-[72px] 2xl:px-[88px]",
        sizes[size],
        className,
      )}
      {...props}
    />
  );
}
