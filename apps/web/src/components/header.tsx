"use client";

import { ArrowRight, Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { copy } from "@/lib/copy";

const links = [
  { href: "/tools", label: copy.nav.tools },
  { href: "/extension", label: copy.nav.extension },
  { href: "/about", label: copy.nav.about },
];

export function Header() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const pathname = usePathname();
  const isActive = (href: string) => pathname === href || pathname.startsWith(`${href}/`);

  // Close the mobile menu on navigation (state adjusted during render, not in an effect).
  const [lastPath, setLastPath] = useState(pathname);
  if (pathname !== lastPath) {
    setLastPath(pathname);
    setOpen(false);
  }

  useEffect(() => {
    // A sentinel at the top of the page: no scroll listener, no layout reads per frame.
    const sentinel = document.getElementById("top-sentinel");
    if (!sentinel || typeof IntersectionObserver === "undefined") {
      return;
    }
    const io = new IntersectionObserver(([entry]) => setScrolled(!entry.isIntersecting));
    io.observe(sentinel);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header
      className={cn(
        "animate-fade-down sticky top-0 z-40 border-b transition-[background-color,border-color,box-shadow] duration-300",
        scrolled || open ? "glass border-border shadow-sm" : "border-transparent bg-transparent",
      )}
    >
      <div className="mx-auto flex min-h-[4.25rem] w-full max-w-[1600px] items-center justify-between gap-4 px-4 sm:px-6 md:px-10 lg:px-14 xl:px-[72px] 2xl:px-[88px]">
        <Link
          href="/"
          className="group rounded-xl transition-transform duration-200 hover:scale-[1.03] active:scale-[0.98]"
          aria-label={`${copy.brand.name} home`}
        >
          <Logo />
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {links.map((link) => {
            const active = isActive(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group relative inline-flex min-h-11 items-center rounded-xl px-3.5 text-sm font-semibold transition-colors duration-200",
                  active ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {link.label}
                <span
                  aria-hidden="true"
                  className={cn(
                    "bg-accent absolute inset-x-3.5 bottom-2 h-0.5 origin-left rounded-full transition-transform duration-300 ease-out",
                    active ? "scale-x-100" : "scale-x-0 group-hover:scale-x-100",
                  )}
                />
              </Link>
            );
          })}
          <span className="bg-border mx-2 h-6 w-px" aria-hidden="true" />
          <ThemeToggle />
          <Button asChild size="sm" className="ml-2 px-4">
            <Link href="/tools">
              {copy.nav.cta}
              <ArrowRight className="transition-transform duration-200 group-hover/button:translate-x-0.5" />
            </Link>
          </Button>
        </nav>

        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          <Button
            variant="outline"
            size="icon"
            aria-expanded={open}
            aria-controls="mobile-nav"
            aria-label={open ? copy.nav.closeMenu : copy.nav.openMenu}
            onClick={() => setOpen((value) => !value)}
          >
            <span className="relative grid size-4 place-items-center">
              <Menu
                className={cn(
                  "absolute transition-[transform,opacity] duration-200",
                  open ? "rotate-90 opacity-0" : "opacity-100",
                )}
              />
              <X
                className={cn(
                  "absolute transition-[transform,opacity] duration-200",
                  open ? "opacity-100" : "-rotate-90 opacity-0",
                )}
              />
            </span>
          </Button>
        </div>
      </div>

      {open ? (
        <nav
          id="mobile-nav"
          className="border-border animate-slide-down border-t px-4 pb-5 pt-3 md:hidden"
          aria-label="Mobile"
        >
          <ul className="space-y-1">
            {links.map((link, index) => (
              <li
                key={link.href}
                className="animate-slide-down"
                style={{ ["--i" as string]: index + 1 }}
              >
                <Link
                  href={link.href}
                  aria-current={isActive(link.href) ? "page" : undefined}
                  className="hover:bg-muted aria-[current=page]:bg-accent-soft aria-[current=page]:text-accent-soft-foreground flex min-h-12 items-center justify-between rounded-xl px-3 text-base font-semibold"
                  onClick={() => setOpen(false)}
                >
                  {link.label}
                  <ArrowRight className="text-muted-foreground size-4" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
          <Button asChild size="lg" className="animate-slide-down mt-3 w-full [--i:4]">
            <Link href="/tools" onClick={() => setOpen(false)}>
              {copy.nav.cta}
              <ArrowRight />
            </Link>
          </Button>
        </nav>
      ) : null}

      <span
        aria-hidden="true"
        className="scroll-progress bg-progress-gradient absolute inset-x-0 bottom-[-1px] h-0.5"
      />
    </header>
  );
}
