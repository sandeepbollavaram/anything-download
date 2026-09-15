import { copy } from "@/lib/copy";

export function SkipLink() {
  return (
    <a
      href="#main"
      className="bg-accent text-accent-foreground sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:px-4 focus:py-2"
    >
      {copy.nav.skip}
    </a>
  );
}
