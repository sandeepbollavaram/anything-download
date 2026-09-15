"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useSyncExternalStore } from "react";

const KEY = "ad-motion";
const listeners = new Set<() => void>();

function read(): boolean {
  if (typeof document === "undefined") return false;
  return document.documentElement.dataset.motion === "paused";
}

export function setMotionPaused(paused: boolean) {
  document.documentElement.dataset.motion = paused ? "paused" : "running";
  try {
    localStorage.setItem(KEY, paused ? "paused" : "running");
  } catch {
    /* Storage blocked: the choice lasts for this page view. */
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Whether decorative motion should run: respects the OS setting and the visitor's toggle. */
export function useMotionAllowed() {
  const paused = useSyncExternalStore(subscribe, read, () => false);
  const reduced = useSyncExternalStore(subscribeReducedMotion, readReducedMotion, () => false);
  return !paused && !reduced;
}

const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeReducedMotion(listener: () => void) {
  const query = window.matchMedia(REDUCED_QUERY);
  query.addEventListener("change", listener);
  return () => query.removeEventListener("change", listener);
}

function readReducedMotion() {
  return window.matchMedia(REDUCED_QUERY).matches;
}

export function MotionToggle({ className }: { className?: string }) {
  const paused = useSyncExternalStore(subscribe, read, () => false);

  useEffect(() => {
    try {
      if (localStorage.getItem(KEY) === "paused") setMotionPaused(true);
    } catch {
      /* ignore */
    }
  }, []);

  return (
    <button
      type="button"
      aria-pressed={paused}
      onClick={() => setMotionPaused(!paused)}
      className={className}
    >
      {paused ? (
        <Play className="size-3.5" aria-hidden="true" />
      ) : (
        <Pause className="size-3.5" aria-hidden="true" />
      )}
      {paused ? "Resume animations" : "Pause animations"}
    </button>
  );
}
