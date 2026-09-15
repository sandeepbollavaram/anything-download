"use client";

import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { MetaphorVisual } from "@/components/metaphor-visual";
import { Button } from "@/components/ui/button";
import { StageList, type Stage, type StageState } from "@/components/ui/feedback";
import { Progress } from "@/components/ui/progress";
import type { JobView } from "@/lib/api";
import { metaphorOf, transformOf } from "@/lib/categories";
import type { CatalogueTool } from "@/lib/catalogue";
import { copy, phaseLabel } from "@/lib/copy";
import { formatBytes } from "@/lib/format";

const PROCESS_LABEL = {
  download: "Preparing your file",
  convert: "Converting",
  compress: "Compressing",
  extract: "Extracting",
  render: "Rendering",
  inspect: "Reading details",
} as const;

/**
 * Builds stages strictly from the job the server reports: status, and the phase the worker
 * published (queued → downloading → processing/rendering → completed). Nothing is timed or
 * simulated. A "Fetching source" stage appears only for link inputs, or once the server has
 * actually reported a download phase.
 */
export function jobStages(
  job: JobView | null,
  tool: CatalogueTool | undefined,
  options: { fromUpload?: boolean; fetchesSource?: boolean; sawDownloading?: boolean },
): Stage[] {
  const status = job?.status ?? "QUEUED";
  const phase = job?.progress?.phase ?? "";
  const failed = status === "FAILED" || status === "CANCELLED" || status === "EXPIRED";
  const includeFetch = Boolean(options.fetchesSource || options.sawDownloading);
  const percent = job?.progress?.percent;
  const percentText = typeof percent === "number" ? `${Math.round(percent)}%` : undefined;

  type Key = "queue" | "fetch" | "process" | "ready";
  let current: Key;
  if (status === "COMPLETED") {
    current = "ready";
  } else if (status === "QUEUED" || !job) {
    current = "queue";
  } else if (phase === "downloading" && includeFetch) {
    current = "fetch";
  } else if (failed && !job.started_at) {
    current = "queue";
  } else {
    current = "process";
  }

  const order: Key[] = ["queue", ...(includeFetch ? (["fetch"] as Key[]) : []), "process", "ready"];
  const currentIndex = order.indexOf(current);
  const stateFor = (key: Key): StageState => {
    const index = order.indexOf(key);
    if (status === "COMPLETED") return "done";
    if (index < currentIndex) return "done";
    if (index === currentIndex) return failed ? "error" : "active";
    return "pending";
  };

  const processLabel =
    phase === "rendering"
      ? "Rendering"
      : (PROCESS_LABEL[metaphorOf(tool)] ?? copy.widget.processing);

  const stages: Stage[] = [];
  if (options.fromUpload) {
    stages.push({ id: "upload", label: "File uploaded", state: "done" });
  }
  stages.push({
    id: "queue",
    label: job ? phaseLabel("queued") : "Starting",
    detail: current === "queue" && !failed ? "Waiting for a free worker" : undefined,
    state: stateFor("queue"),
  });
  if (includeFetch) {
    stages.push({
      id: "fetch",
      label: "Fetching the source",
      detail: current === "fetch" ? percentText : undefined,
      state: stateFor("fetch"),
    });
  }
  stages.push({
    id: "process",
    label: processLabel,
    detail:
      current === "process" && !failed
        ? job?.progress?.message || percentText || undefined
        : undefined,
    state: stateFor("process"),
  });
  stages.push({ id: "ready", label: "Ready to download", state: stateFor("ready") });
  return stages;
}

export function ProcessingCard({
  job,
  tool,
  fromUpload,
  fetchesSource,
  fromLabel,
  inputSize,
  outputLabel,
  onCancel,
  headingLevel = "h2",
}: {
  job: JobView | null;
  tool: CatalogueTool | undefined;
  fromUpload?: boolean;
  fetchesSource?: boolean;
  fromLabel?: string;
  inputSize?: number | null;
  outputLabel?: string;
  onCancel?: () => void;
  headingLevel?: "h2" | "h3";
}) {
  // Remember that the server reported a download phase, so the stage stays listed afterwards.
  const [sawDownloading, setSawDownloading] = useState(false);
  if (job?.progress?.phase === "downloading" && !sawDownloading) {
    setSawDownloading(true);
  }
  const stages = jobStages(job, tool, { fromUpload, fetchesSource, sawDownloading });
  const active = stages.find((stage) => stage.state === "active");
  const percent = job?.progress?.percent;
  const transform = transformOf(tool);
  const from = fromLabel || transform?.from;
  const to = outputLabel || transform?.to;
  const Heading = headingLevel;

  return (
    <section
      aria-label={copy.widget.jobHeading}
      className="surface-raised animate-scale-in overflow-hidden rounded-3xl"
    >
      <div className="grid gap-6 p-5 sm:p-7 md:grid-cols-[minmax(0,1fr)_minmax(0,15rem)] md:items-center">
        <div className="min-w-0 space-y-5">
          <div>
            <p className="text-muted-foreground text-xs font-bold uppercase tracking-[0.16em]">
              {tool?.name ?? copy.widget.jobHeading}
            </p>
            <Heading className="font-display mt-1 text-2xl font-extrabold">
              {active?.label ?? copy.widget.processing}
            </Heading>
          </div>
          <Progress
            value={typeof percent === "number" ? percent : null}
            label={
              typeof percent === "number"
                ? phaseLabel(job?.progress?.phase || "processing")
                : job?.progress?.message || copy.widget.processing
            }
          />
          <StageList stages={stages} />
        </div>
        <div className="bg-background-alt flex flex-col items-center gap-4 rounded-2xl p-5 text-center">
          <MetaphorVisual metaphor={metaphorOf(tool)} />
          {from || to ? (
            <p className="font-display flex flex-wrap items-center justify-center gap-2 text-sm font-bold">
              {from ? <span className="bg-card shadow-xs rounded-lg px-2 py-1">{from}</span> : null}
              {from && to ? <ArrowRight className="text-accent size-4" aria-label="to" /> : null}
              {to ? (
                <span className="bg-accent-soft text-accent-soft-foreground rounded-lg px-2 py-1">
                  {to}
                </span>
              ) : null}
            </p>
          ) : null}
          {inputSize ? (
            <p className="text-muted-foreground text-xs">
              Input {formatBytes(inputSize)} · output size shown when ready
            </p>
          ) : null}
        </div>
      </div>
      {onCancel ? (
        <div className="border-border bg-background-alt/60 flex items-center justify-between gap-3 border-t px-5 py-3 sm:px-7">
          <p className="text-muted-foreground text-xs">
            You can leave this page open. It updates live.
          </p>
          <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
            {copy.widget.cancel}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
