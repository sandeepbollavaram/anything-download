"use client";

import {
  ArrowLeft,
  Check,
  ChevronDown,
  Copy,
  Download,
  Info,
  RotateCcw,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { CategoryIcon } from "@/components/category-icon";
import { ProcessingCard } from "@/components/processing-card";
import { StatusPanel } from "@/components/status-panel";
import { StructuredData } from "@/components/structured-data";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton, SuccessMark } from "@/components/ui/feedback";
import {
  cancelJob,
  deleteJob,
  getJob,
  getLimits,
  isTerminalStatus,
  jobResultUrl,
  toErrorPayload,
  type ErrorPayload,
  type JobView,
} from "@/lib/api";
import { getCatalogueTool, TOOL_CATALOGUE } from "@/lib/catalogue";
import { cn } from "@/lib/cn";
import { copy, noteLabel } from "@/lib/copy";
import { formatBytes, formatCountdown, remainingMs } from "@/lib/format";

export function ResultClient({ id }: { id: string }) {
  const [job, setJob] = useState<JobView | null>(null);
  const [error, setError] = useState<ErrorPayload | null>(null);
  const [deleted, setDeleted] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [ttlSeconds, setTtlSeconds] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function load() {
      try {
        const next = await getJob(id);
        if (cancelled) {
          return;
        }
        setJob(next);
        setError(next.error ?? null);
        if (!isTerminalStatus(next.status)) {
          timer = window.setTimeout(() => {
            void load();
          }, 1000);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(toErrorPayload(caught));
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
      if (timer) {
        window.clearTimeout(timer);
      }
    };
  }, [id]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    void getLimits().then((limits) => setTtlSeconds(limits?.result_ttl_seconds ?? null));
  }, []);

  async function onDelete() {
    try {
      await deleteJob(id);
      setDeleted(true);
      setConfirmOpen(false);
    } catch (caught) {
      setError(toErrorPayload(caught));
      setConfirmOpen(false);
    }
  }

  async function onCancel() {
    try {
      const next = await cancelJob(id);
      setJob(next);
    } catch (caught) {
      setError(toErrorPayload(caught));
    }
  }

  if (deleted) {
    return (
      <Shell>
        <h1 className="font-display text-4xl font-extrabold">{copy.result.heading}</h1>
        <div className="surface-raised animate-scale-in flex flex-col items-center gap-4 rounded-3xl px-6 py-14 text-center">
          <span className="bg-success-soft text-success grid size-14 place-items-center rounded-full">
            <Trash2 className="size-6" aria-hidden="true" />
          </span>
          <p className="font-display text-xl font-bold" role="status">
            {copy.result.deleted}
          </p>
          <p className="text-muted-foreground text-sm">Nothing is left on the server.</p>
          <Button asChild variant="outline">
            <Link href="/">{copy.result.backHome}</Link>
          </Button>
        </div>
      </Shell>
    );
  }

  if (!job && !error) {
    return (
      <Shell>
        <p className="sr-only" role="status">
          {copy.a11y.loading}
        </p>
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-12 w-72" />
        <Skeleton className="h-72 w-full rounded-3xl" />
      </Shell>
    );
  }

  if (!job && error) {
    return (
      <Shell>
        <h1 className="font-display text-4xl font-extrabold">{copy.result.heading}</h1>
        <StatusPanel error={{ ...error, message: error.message || copy.errors.jobNotFound }}>
          <Button asChild variant="outline" size="sm">
            <Link href="/">{copy.result.backHome}</Link>
          </Button>
        </StatusPanel>
      </Shell>
    );
  }

  if (!job) {
    return null;
  }

  const tool = getCatalogueTool(job.tool);
  const file = job.result?.file;
  const resultHref = job.result_url ? jobResultUrl(job.id) : null;
  const remaining = remainingMs(job.expires_at);
  const msLeft = job.expires_at ? new Date(job.expires_at).getTime() - now : null;
  const liveCountdown =
    job.expires_at && remaining != null && msLeft != null ? formatCountdown(msLeft) : null;
  const hasFailed =
    job.status === "FAILED" || job.status === "CANCELLED" || job.status === "EXPIRED";
  const completed = job.status === "COMPLETED";
  const related = tool
    ? TOOL_CATALOGUE.filter((item) => item.category === tool.category && item.id !== tool.id).slice(
        0,
        3,
      )
    : [];

  return (
    <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-w-0 space-y-6">
        <div className="animate-fade-up space-y-3">
          {tool ? (
            <Link
              href={`/tools/${tool.id}`}
              className="text-muted-foreground hover:text-foreground group inline-flex min-h-11 items-center gap-2.5 text-sm font-semibold"
            >
              <ArrowLeft
                className="size-4 transition-transform group-hover:-translate-x-0.5"
                aria-hidden="true"
              />
              <CategoryIcon category={tool.category} size="sm" />
              {tool.name}
            </Link>
          ) : null}
          <h1 className="font-display text-4xl font-extrabold leading-tight sm:text-5xl">
            {copy.result.heading}
          </h1>
        </div>

        {/* Progress only. A terminal failure is announced once, by the role="alert" below. */}
        <div className="sr-only" aria-live="polite">
          {hasFailed ? "" : completed ? "Your file is ready." : job.progress?.message || job.status}
        </div>

        {!isTerminalStatus(job.status) ? (
          <ProcessingCard job={job} tool={tool} onCancel={() => void onCancel()} />
        ) : null}

        {hasFailed ? (
          <StatusPanel
            error={
              job.error ?? {
                code: job.status,
                message:
                  job.status === "EXPIRED"
                    ? copy.result.expired
                    : job.status === "CANCELLED"
                      ? copy.result.cancelled
                      : copy.result.failed,
                retryable: false,
              }
            }
          >
            {tool ? (
              <Button asChild variant="outline" size="sm">
                <Link href={`/tools/${tool.id}`}>
                  <RotateCcw />
                  Try again
                </Link>
              </Button>
            ) : null}
          </StatusPanel>
        ) : null}

        {completed && file ? (
          <ResultSurface
            job={job}
            file={file}
            resultHref={resultHref}
            onDelete={() => setConfirmOpen(true)}
          />
        ) : null}

        {completed && !file && !job.result?.data ? (
          <p className="text-muted-foreground">{copy.result.notReady}</p>
        ) : null}

        {job.result?.data ? <DataPanel data={job.result.data} defaultOpen={!file} /> : null}

        {error && job && !hasFailed ? <StatusPanel error={error} /> : null}
      </div>

      <aside className="space-y-5 lg:sticky lg:top-24" aria-label="File details">
        {completed ? (
          <ExpiryCard
            msLeft={msLeft}
            ttlSeconds={ttlSeconds}
            label={
              liveCountdown && file
                ? liveCountdown.label === "now"
                  ? copy.result.expiryNow
                  : copy.result.expiry(liveCountdown.label)
                : null
            }
          />
        ) : null}
        <div className="surface rounded-2xl p-5">
          <p className="text-muted-foreground mb-3 text-xs font-bold uppercase tracking-[0.16em]">
            Private by design
          </p>
          <ul className="space-y-2.5 text-sm">
            {[
              "Only people with this page's address can open it.",
              "Nothing is tied to an account, because there isn't one.",
              "You can delete the file now instead of waiting.",
            ].map((item) => (
              <li key={item} className="flex gap-2.5">
                <ShieldCheck className="text-success mt-0.5 size-4 shrink-0" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        {related.length ? (
          <div className="surface rounded-2xl p-5">
            <p className="text-muted-foreground mb-2 text-xs font-bold uppercase tracking-[0.16em]">
              Try next
            </p>
            <ul>
              {related.map((item, index) => (
                <li key={item.id} className="animate-fade-up" style={{ ["--i" as string]: index }}>
                  <Link
                    href={`/tools/${item.id}`}
                    className="hover:bg-muted -mx-2 flex min-h-11 items-center gap-3 rounded-xl px-2 py-1.5 text-sm font-semibold"
                  >
                    <CategoryIcon category={item.category} size="sm" />
                    {item.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </aside>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{copy.result.deleteConfirmTitle}</DialogTitle>
            <DialogDescription>{copy.result.deleteConfirm}</DialogDescription>
          </DialogHeader>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button type="button" variant="destructive" onClick={() => void onDelete()}>
              {copy.result.deleteConfirmAction}
            </Button>
            <Button type="button" variant="outline" onClick={() => setConfirmOpen(false)}>
              {copy.widget.cancel}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-3xl space-y-6">{children}</div>;
}

function ResultSurface({
  job,
  file,
  resultHref,
  onDelete,
}: {
  job: JobView;
  file: NonNullable<NonNullable<JobView["result"]>["file"]>;
  resultHref: string | null;
  onDelete: () => void;
}) {
  const [started, setStarted] = useState(false);
  const [copied, setCopied] = useState(false);
  const ext = file.filename.includes(".") ? file.filename.split(".").pop()?.toUpperCase() : null;
  const previewSafe =
    file.mime_type.startsWith("image/") ||
    file.mime_type.startsWith("audio/") ||
    file.mime_type.startsWith("video/") ||
    file.mime_type === "application/pdf";

  useEffect(() => {
    if (!started) return;
    const timer = window.setTimeout(() => setStarted(false), 4000);
    return () => window.clearTimeout(timer);
  }, [started]);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
    } catch {
      /* Clipboard unavailable; the address bar still has the link. */
    }
  }

  return (
    <section
      aria-labelledby="result-file-heading"
      className="surface-raised animate-scale-in overflow-hidden rounded-3xl"
    >
      <div className="flex flex-wrap items-center gap-4 p-5 sm:p-7">
        <SuccessMark />
        <div className="min-w-0 flex-1">
          <p className="text-success text-sm font-bold">Ready</p>
          <h2
            id="result-file-heading"
            className="font-display animate-fade-up break-words text-xl font-extrabold [--ad-delay:120ms] sm:text-2xl"
          >
            {file.filename || copy.result.dataHeading}
          </h2>
          <dl className="mt-2 flex flex-wrap gap-2 text-xs">
            {[
              { label: copy.result.size, value: formatBytes(file.size_bytes) },
              { label: copy.result.format, value: ext || file.mime_type },
              { label: "Type", value: file.mime_type },
            ].map((item, index) => (
              <div
                key={item.label}
                className="bg-muted animate-fade-up flex gap-1 rounded-lg px-2 py-1"
                style={{ ["--i" as string]: index + 3 }}
              >
                <dt className="text-muted-foreground">{item.label}</dt>
                <dd className="font-semibold">{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {previewSafe && resultHref ? (
        <div className="border-border bg-background-alt/60 border-y p-4 sm:p-6">
          <p className="text-muted-foreground mb-3 text-xs font-bold uppercase tracking-[0.16em]">
            {copy.result.preview}
          </p>
          <ResultPreview mime={file.mime_type} href={resultHref} filename={file.filename} />
        </div>
      ) : null}

      {job.result?.notes?.length ? (
        <ul className="text-muted-foreground space-y-1 px-5 pt-4 text-sm sm:px-7">
          {job.result.notes.map((note) => (
            <li key={note} className="flex gap-2">
              <Info className="text-accent mt-0.5 size-4 shrink-0" aria-hidden="true" />
              {noteLabel(note)}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 p-5 sm:p-7">
        {resultHref ? (
          <Button asChild size="xl" className="min-w-44">
            <a href={resultHref} download={file.filename} onClick={() => setStarted(true)}>
              <Download className="transition-transform duration-300 group-hover/button:translate-y-0.5" />
              {copy.result.download}
            </a>
          </Button>
        ) : null}
        {job.tool ? (
          <Button asChild variant="outline" size="lg">
            <Link href={`/tools/${job.tool}`}>
              <RotateCcw />
              Process another
            </Link>
          </Button>
        ) : null}
        <Button type="button" variant="ghost" size="lg" onClick={() => void copyLink()}>
          {copied ? <Check className="text-success animate-pop" /> : <Copy />}
          {copied ? "Link copied" : "Copy link"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="lg"
          className="text-destructive hover:bg-destructive-soft sm:ml-auto"
          onClick={onDelete}
        >
          <Trash2 />
          {copy.result.delete}
        </Button>
        <p role="status" aria-live="polite" className="text-success w-full text-sm font-semibold">
          {started ? (
            <span className="animate-fade-in inline-flex items-center gap-1.5">
              <Check className="size-4" aria-hidden="true" />
              Download started. Check your browser&apos;s downloads.
            </span>
          ) : null}
        </p>
      </div>
    </section>
  );
}

function ExpiryCard({
  msLeft,
  ttlSeconds,
  label,
}: {
  msLeft: number | null;
  ttlSeconds: number | null;
  label: string | null;
}) {
  if (msLeft == null || !label) {
    return null;
  }
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  // The ring only shows a fraction when the real retention window is known from /limits.
  const fraction = ttlSeconds ? Math.max(0, Math.min(1, msLeft / (ttlSeconds * 1000))) : null;
  const countdown = formatCountdown(msLeft);

  return (
    <div className="surface animate-fade-up flex items-center gap-4 rounded-2xl p-5">
      <div className="relative grid size-16 shrink-0 place-items-center" aria-hidden="true">
        <svg viewBox="0 0 64 64" className="absolute inset-0 -rotate-90">
          <circle cx="32" cy="32" r={radius} fill="none" stroke="var(--muted)" strokeWidth="6" />
          {fraction != null ? (
            <circle
              cx="32"
              cy="32"
              r={radius}
              fill="none"
              stroke="var(--accent)"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - fraction)}
              className="transition-[stroke-dashoffset] duration-1000 ease-linear"
            />
          ) : null}
        </svg>
        <span className="font-mono text-xs font-bold tabular-nums">
          {countdown.minutes}:{String(countdown.seconds).padStart(2, "0")}
        </span>
      </div>
      <div>
        <p className="text-muted-foreground text-xs font-bold uppercase tracking-[0.16em]">
          Auto-delete
        </p>
        <p className="text-sm font-medium">{label}</p>
      </div>
    </div>
  );
}

function DataPanel({ data, defaultOpen }: { data: Record<string, unknown>; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section
      className="surface animate-fade-up overflow-hidden rounded-2xl"
      aria-labelledby="data-heading"
    >
      <h2 id="data-heading" className="m-0">
        <button
          type="button"
          aria-expanded={open}
          aria-controls="data-body"
          onClick={() => setOpen((value) => !value)}
          className="hover:bg-muted/60 font-display flex min-h-14 w-full cursor-pointer items-center justify-between gap-3 px-5 text-left text-lg font-bold"
        >
          {copy.result.dataHeading}
          <ChevronDown
            className={cn("size-5 transition-transform duration-300", open && "rotate-180")}
            aria-hidden="true"
          />
        </button>
      </h2>
      <div
        id="data-body"
        className={cn(
          "grid transition-[grid-template-rows] duration-300 ease-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
        inert={!open}
      >
        <div className="overflow-hidden">
          <div className="border-border border-t p-5">
            <StructuredData data={data} />
          </div>
        </div>
      </div>
    </section>
  );
}

function ResultPreview({ mime, href, filename }: { mime: string; href: string; filename: string }) {
  const [loaded, setLoaded] = useState(false);
  const [playing, setPlaying] = useState(false);

  if (mime.startsWith("image/")) {
    return (
      <div className="bg-card relative grid min-h-40 place-items-center overflow-hidden rounded-2xl border">
        {!loaded ? <Skeleton className="absolute inset-0 rounded-none" /> : null}
        {/* Result files are same-origin via the API rewrite, not remote next/image hosts. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={href}
          alt={filename}
          onLoad={() => setLoaded(true)}
          className={cn(
            "relative max-h-[28rem] w-auto transition-[opacity,transform] duration-700 ease-out",
            loaded ? "scale-100 opacity-100" : "scale-[0.97] opacity-0",
          )}
        />
      </div>
    );
  }
  if (mime.startsWith("audio/")) {
    return (
      <div className="bg-card flex flex-col gap-4 rounded-2xl border p-4 sm:flex-row sm:items-center">
        <div aria-hidden="true" className="flex h-10 items-end gap-1 px-2">
          {Array.from({ length: 14 }, (_, index) => (
            <span
              key={index}
              className={cn("bg-accent w-1.5 rounded-full", playing ? "bar-dance" : "")}
              style={{
                height: `${30 + ((index * 37) % 70)}%`,
                ["--i" as string]: index,
                opacity: playing ? 1 : 0.35,
              }}
            />
          ))}
        </div>
        <audio
          controls
          src={href}
          className="w-full"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
        />
      </div>
    );
  }
  if (mime.startsWith("video/")) {
    return (
      <video
        controls
        src={href}
        onLoadedData={() => setLoaded(true)}
        className={cn(
          "max-h-[28rem] w-full rounded-2xl border bg-black transition-opacity duration-700",
          loaded ? "opacity-100" : "opacity-60",
        )}
      />
    );
  }
  if (mime === "application/pdf") {
    return (
      <iframe
        title={filename}
        src={href}
        onLoad={() => setLoaded(true)}
        className={cn(
          "bg-card h-[28rem] w-full rounded-2xl border transition-[opacity,transform] duration-700 ease-out",
          loaded ? "translate-y-0 opacity-100" : "translate-y-1 opacity-60",
        )}
      />
    );
  }
  return null;
}
