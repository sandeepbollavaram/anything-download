"use client";

import { ArrowRight, Search, SearchX, X } from "lucide-react";
import Link from "next/link";
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { CategoryIcon } from "@/components/category-icon";
import { ToolCard } from "@/components/tool-card";
import { Button } from "@/components/ui/button";
import { CATEGORIES } from "@/lib/categories";
import type { CatalogueTool, ToolCategory } from "@/lib/catalogue";
import { cn } from "@/lib/cn";

type Filter = "all" | ToolCategory;

/**
 * Searchable, filterable tool catalogue.
 * - Search filters instantly (deferred so typing never stutters).
 * - Category tabs are a real tablist: ←/→/Home/End move between tabs.
 * - Cards support arrow-key navigation across the grid.
 * - "/" focuses search from anywhere on the page (not while typing in a field).
 */
export function ToolExplorer({
  tools,
  unavailable = [],
  catalogueOnly = false,
  limit,
  headingLevel = "h2",
  syncHash = false,
  idPrefix = "explorer",
}: {
  tools: CatalogueTool[];
  unavailable?: string[];
  catalogueOnly?: boolean;
  /** Show at most this many results, with a link to the full catalogue. */
  limit?: number;
  headingLevel?: "h2" | "h3";
  syncHash?: boolean;
  idPrefix?: string;
}) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const deferredQuery = useDeferredValue(query);
  const searchRef = useRef<HTMLInputElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const unavailableSet = useMemo(() => new Set(unavailable), [unavailable]);

  useEffect(() => {
    if (!syncHash) return;
    const fromHash = window.location.hash.replace("#", "");
    if (!CATEGORIES.some((category) => category.id === fromHash)) return;
    // Applied after hydration so server and client render the same first frame.
    const frame = window.requestAnimationFrame(() => setFilter(fromHash as ToolCategory));
    return () => window.cancelAnimationFrame(frame);
  }, [syncHash]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable);
      if (event.key === "/" && !typing && !event.metaKey && !event.ctrlKey) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const counts = useMemo(() => {
    const result: Record<string, number> = { all: tools.length };
    for (const tool of tools) result[tool.category] = (result[tool.category] ?? 0) + 1;
    return result;
  }, [tools]);

  const results = useMemo(() => {
    const terms = deferredQuery.trim().toLowerCase().split(/\s+/).filter(Boolean);
    return tools.filter((tool) => {
      if (filter !== "all" && tool.category !== filter) return false;
      if (terms.length === 0) return true;
      const haystack =
        `${tool.name} ${tool.short} ${tool.description} ${tool.category}`.toLowerCase();
      return terms.every((term) => haystack.includes(term));
    });
  }, [tools, filter, deferredQuery]);

  const visible = limit ? results.slice(0, limit) : results;
  const filters: Array<{ id: Filter; label: string }> = [
    { id: "all", label: "All" },
    ...CATEGORIES.filter((category) => counts[category.id]).map((category) => ({
      id: category.id,
      label: category.label,
    })),
  ];

  const selectFilter = useCallback(
    (next: Filter) => {
      setFilter(next);
      if (syncHash) {
        const url = next === "all" ? window.location.pathname : `#${next}`;
        window.history.replaceState(null, "", url);
      }
    },
    [syncHash],
  );

  function onGridKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    const keys = ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"];
    if (!keys.includes(event.key)) return;
    const cards = Array.from(
      gridRef.current?.querySelectorAll<HTMLElement>("[data-tool-card]") ?? [],
    );
    const index = cards.indexOf(document.activeElement as HTMLElement);
    if (index < 0) return;
    event.preventDefault();
    const top = cards[0]?.offsetTop ?? 0;
    const columns = Math.max(1, cards.filter((card) => card.offsetTop === top).length);
    const delta =
      event.key === "ArrowRight"
        ? 1
        : event.key === "ArrowLeft"
          ? -1
          : event.key === "ArrowDown"
            ? columns
            : -columns;
    cards[Math.min(cards.length - 1, Math.max(0, index + delta))]?.focus();
  }

  const Heading = headingLevel;
  const resultKey = `${filter}|${deferredQuery}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <FilterTabs
          filters={filters}
          counts={counts}
          active={filter}
          onSelect={selectFilter}
          panelId={`${idPrefix}-results`}
        />
        <div className="relative w-full lg:max-w-sm">
          <Search
            className="text-muted-foreground pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2"
            aria-hidden="true"
          />
          <label htmlFor={`${idPrefix}-search`} className="sr-only">
            Search tools
          </label>
          <input
            ref={searchRef}
            id={`${idPrefix}-search`}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search: mp3, compress, pdf…"
            autoComplete="off"
            className="border-input/50 bg-card placeholder:text-muted-foreground hover:border-input focus-visible:border-accent focus-visible:ring-accent/15 shadow-xs min-h-12 w-full rounded-xl border pl-10 pr-20 text-base transition-[border-color,box-shadow] focus-visible:outline-none focus-visible:ring-4 [&::-webkit-search-cancel-button]:hidden"
          />
          {query ? (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                searchRef.current?.focus();
              }}
              className="text-muted-foreground hover:text-foreground hover:bg-muted absolute right-1.5 top-1/2 grid size-9 -translate-y-1/2 place-items-center rounded-lg"
              aria-label="Clear search"
            >
              <X className="size-4" />
            </button>
          ) : (
            <kbd
              aria-hidden="true"
              className="border-border text-muted-foreground absolute right-3 top-1/2 hidden -translate-y-1/2 rounded-md border px-1.5 py-0.5 font-mono text-xs sm:block"
            >
              /
            </kbd>
          )}
        </div>
      </div>

      <p className="sr-only" aria-live="polite">
        {results.length === 1 ? "1 tool" : `${results.length} tools`}
        {filter !== "all" ? ` in ${filters.find((item) => item.id === filter)?.label}` : ""}
        {deferredQuery ? ` matching ${deferredQuery}` : ""}
      </p>

      <div
        id={`${idPrefix}-results`}
        role="tabpanel"
        aria-labelledby={`${idPrefix}-tab-${filter}`}
        ref={gridRef}
        onKeyDown={onGridKeyDown}
      >
        {visible.length === 0 ? (
          <div className="surface animate-scale-in flex flex-col items-center gap-3 rounded-2xl px-6 py-14 text-center">
            <span className="bg-muted text-muted-foreground grid size-14 place-items-center rounded-2xl">
              <SearchX
                className="animate-drift size-6 [--ad-drift-dur:3s] [--ad-rot:-6deg]"
                aria-hidden="true"
              />
            </span>
            <Heading className="font-display text-lg font-bold">
              No tools match “{deferredQuery}”
            </Heading>
            <p className="text-muted-foreground max-w-sm text-sm">
              Try a format (mp3, webp, pdf) or an action (compress, merge, extract).
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setQuery("");
                selectFilter("all");
              }}
            >
              Clear filters
            </Button>
          </div>
        ) : (
          <ul key={resultKey} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {visible.map((tool, index) => (
              <li
                key={tool.id}
                className="animate-fade-up"
                style={{ ["--i" as string]: Math.min(index, 12) }}
              >
                <ToolCard
                  tool={tool}
                  unavailable={unavailableSet.has(tool.id)}
                  catalogueOnly={catalogueOnly}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      {limit && results.length > limit ? (
        <div className="flex justify-center">
          <Button asChild variant="outline" size="lg">
            <Link href={filter === "all" ? "/tools" : `/tools#${filter}`}>
              See all {results.length} tools
              <ArrowRight className="transition-transform group-hover/button:translate-x-0.5" />
            </Link>
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function FilterTabs({
  filters,
  counts,
  active,
  onSelect,
  panelId,
}: {
  filters: Array<{ id: Filter; label: string }>;
  counts: Record<string, number>;
  active: Filter;
  onSelect: (filter: Filter) => void;
  panelId: string;
}) {
  const listRef = useRef<HTMLDivElement>(null);
  const [indicator, setIndicator] = useState<{ left: number; width: number } | null>(null);
  const prefix = panelId.replace(/-results$/, "");

  useLayoutEffect(() => {
    const button = listRef.current?.querySelector<HTMLElement>(`[data-filter="${active}"]`);
    if (button) {
      setIndicator({ left: button.offsetLeft, width: button.offsetWidth });
      // Keep the active tab in view horizontally on small screens, without scrolling the page.
      const scroller = listRef.current?.parentElement;
      if (scroller && scroller.scrollWidth > scroller.clientWidth) {
        const start = button.offsetLeft - 16;
        const end = button.offsetLeft + button.offsetWidth + 16 - scroller.clientWidth;
        if (scroller.scrollLeft > start) scroller.scrollLeft = start;
        else if (scroller.scrollLeft < end) scroller.scrollLeft = end;
      }
    }
  }, [active, filters.length]);

  function onKeyDown(event: React.KeyboardEvent) {
    const index = filters.findIndex((item) => item.id === active);
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % filters.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + filters.length) % filters.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = filters.length - 1;
    else return;
    event.preventDefault();
    onSelect(filters[next].id);
    listRef.current?.querySelector<HTMLElement>(`[data-filter="${filters[next].id}"]`)?.focus();
  }

  return (
    <div className="scrollbar-none -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <div
        ref={listRef}
        role="tablist"
        aria-label="Tool categories"
        onKeyDown={onKeyDown}
        className="bg-muted relative inline-flex min-w-max gap-1 rounded-2xl p-1"
      >
        {indicator ? (
          <span
            aria-hidden="true"
            className="bg-card absolute inset-y-1 rounded-xl shadow-sm transition-[left,width] duration-300 ease-out"
            style={{ left: indicator.left, width: indicator.width }}
          />
        ) : null}
        {filters.map((item) => {
          const selected = item.id === active;
          return (
            <button
              key={item.id}
              id={`${prefix}-tab-${item.id}`}
              type="button"
              role="tab"
              data-filter={item.id}
              aria-selected={selected}
              aria-controls={panelId}
              tabIndex={selected ? 0 : -1}
              onClick={() => onSelect(item.id)}
              className={cn(
                "relative z-10 inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-xl px-3.5 text-sm font-semibold transition-colors duration-200",
                selected ? "text-foreground" : "text-muted-foreground hover:text-foreground",
                !indicator && selected && "bg-card shadow-sm",
              )}
            >
              {item.id !== "all" ? (
                <CategoryIcon
                  category={item.id}
                  size="sm"
                  className="size-6 rounded-md [&_svg]:size-3.5"
                />
              ) : null}
              {item.label}
              <span className="text-muted-foreground font-mono text-xs tabular-nums">
                {counts[item.id]}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
