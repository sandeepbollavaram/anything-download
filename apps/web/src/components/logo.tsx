import Image from "next/image";

import { cn } from "@/lib/cn";
import { copy } from "@/lib/copy";

/**
 * Brand lockup: the owner's logo mark plus a live-text wordmark in the logo's two colours
 * ("Anything" in ink, "Download" in blue), so the name stays crisp at any size.
 * In dark mode the mark sits on a light tile because its navy tray would disappear.
 */
export function Logo({
  className,
  markOnly = false,
  size = "md",
}: {
  className?: string;
  markOnly?: boolean;
  size?: "md" | "lg";
}) {
  const px = size === "lg" ? 48 : 36;
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span className="inline-grid shrink-0 place-items-center rounded-xl transition-transform duration-300 group-hover:-rotate-6 dark:bg-white dark:p-1">
        <Image
          src={size === "lg" ? "/brand/mark-192.png" : "/brand/mark-96.png"}
          width={px}
          height={px}
          alt=""
          priority
        />
      </span>
      {markOnly ? (
        <span className="sr-only">{copy.brand.name}</span>
      ) : (
        <span
          className={cn(
            "font-display font-extrabold leading-none",
            size === "lg" ? "text-2xl" : "text-lg",
          )}
        >
          Anything <span className="text-link">Download</span>
        </span>
      )}
    </span>
  );
}
