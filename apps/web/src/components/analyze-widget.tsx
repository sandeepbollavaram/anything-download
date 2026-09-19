"use client";

import { ArrowRight, Check, ClipboardPaste, Globe, Link2, Lock, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { AnalysisResult } from "@/components/analysis-result";
import { CategoryIcon } from "@/components/category-icon";
import { FileDropzone } from "@/components/file-dropzone";
import { ProcessingCard } from "@/components/processing-card";
import { StatusPanel } from "@/components/status-panel";
import { ToolOptions } from "@/components/tool-options";
import { Button } from "@/components/ui/button";
import { Spinner, StageList, type Stage } from "@/components/ui/feedback";
import { Input, Label, Textarea } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  analyzeUrl,
  assertUploadSize,
  cancelJob,
  createJob,
  getJob,
  getLimits,
  getUpload,
  isTerminalStatus,
  listTools,
  toErrorPayload,
  uploadFile,
  type ErrorPayload,
  type JobView,
  type Limits,
  type URLAnalysis,
  type UploadView,
} from "@/lib/api";
import { getCatalogueTool, toolsNotNeedingSource } from "@/lib/catalogue";
import { cn } from "@/lib/cn";
import { copy, phaseLabel } from "@/lib/copy";
import { formatBytes } from "@/lib/format";
import { collectOptions, optionFieldsForTool, type OptionField } from "@/lib/options";

type WidgetProps = {
  preselectedTool?: string;
  initialUrl?: string;
  initialUploadId?: string;
  redirectOnSubmit?: boolean;
  /** `hero`: compact single panel for the home page. `workspace`: panel plus live journey sidebar. */
  layout?: "hero" | "workspace";
  /** Extra sidebar content (workspace layout only). */
  aside?: React.ReactNode;
};

type LiveState = "idle" | "uploading" | "analyzing" | "ready" | "running" | "error";

type UploadMeter = { percent: number | null; bytesPerSecond: number | null; name: string };

const FORMAT_HINTS = ["Video", "Audio", "Images", "PDF", "Web pages"];

const noopSubscribe = () => () => undefined;

export function AnalyzeWidget({
  preselectedTool,
  initialUrl = "",
  initialUploadId,
  redirectOnSubmit = false,
  layout = "workspace",
  aside,
}: WidgetProps) {
  const router = useRouter();
  const catalogue = preselectedTool ? getCatalogueTool(preselectedTool) : undefined;
  const inputKinds = catalogue?.inputs ?? ["url", "upload"];
  const textOnly = inputKinds.length === 1 && inputKinds[0] === "text";
  const uploadsOnly =
    !inputKinds.includes("url") &&
    !inputKinds.includes("text") &&
    inputKinds.some((kind) => kind === "upload" || kind === "uploads");
  const multiUpload = inputKinds.includes("uploads");
  const urlOnly = !textOnly && !inputKinds.some((kind) => kind === "upload" || kind === "uploads");

  const [url, setUrl] = useState(initialUrl);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [uploads, setUploads] = useState<UploadView[]>([]);
  const [analysis, setAnalysis] = useState<URLAnalysis | null>(null);
  const [selectedTool, setSelectedTool] = useState(preselectedTool ?? "");
  const [optionOverrides, setOptionOverrides] = useState<Record<string, string | boolean>>({});
  const [state, setState] = useState<LiveState>("idle");
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState<ErrorPayload | null>(null);
  const [job, setJob] = useState<JobView | null>(null);
  const [uploadMeter, setUploadMeter] = useState<UploadMeter | null>(null);
  const [runtimeUnavailable, setRuntimeUnavailable] = useState<Set<string>>(new Set());
  const [justPasted, setJustPasted] = useState(false);
  const canPaste = useSyncExternalStore(
    noopSubscribe,
    () => Boolean(navigator.clipboard?.readText),
    () => false,
  );
  const [errorNonce, setErrorNonce] = useState(0);
  const resultsRef = useRef<HTMLHeadingElement>(null);
  const urlRef = useRef<HTMLInputElement>(null);
  const autoStarted = useRef(false);
  const processingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    void listTools()
      .then((response) => {
        if (cancelled) {
          return;
        }
        setRuntimeUnavailable(
          new Set(response.tools.filter((tool) => !tool.available).map((tool) => tool.id)),
        );
      })
      .catch(() => {
        /* Catalogue pages still work; Start will surface a typed API error. */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (state !== "running" || !processingRef.current) {
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    processingRef.current.scrollIntoView({
      block: "nearest",
      behavior: reduce ? "auto" : "smooth",
    });
  }, [state]);

  useEffect(() => {
    if (!justPasted) {
      return;
    }
    const timer = window.setTimeout(() => setJustPasted(false), 900);
    return () => window.clearTimeout(timer);
  }, [justPasted]);

  const availableToolIds = useMemo(() => {
    const dropUnavailable = (ids: string[]) => ids.filter((id) => !runtimeUnavailable.has(id));
    if (analysis) {
      return dropUnavailable(analysis.tools);
    }
    if (uploads.length === 1) {
      return dropUnavailable(uploads[0].tools);
    }
    if (uploads.length > 1) {
      const sets = uploads.map((item) => new Set(item.tools));
      return dropUnavailable([...sets[0]].filter((id) => sets.every((set) => set.has(id))));
    }
    if (preselectedTool && !runtimeUnavailable.has(preselectedTool)) {
      return [preselectedTool];
    }
    return [];
  }, [analysis, uploads, preselectedTool, runtimeUnavailable]);

  const blocked = analysis?.status === "unsupported" || analysis?.status === "restricted";

  const optionFields: OptionField[] = useMemo(
    () => optionFieldsForTool(selectedTool, analysis?.formats),
    [selectedTool, analysis?.formats],
  );

  const optionDefaults = useMemo(() => {
    const defaults: Record<string, string | boolean> = {};
    for (const field of optionFields) {
      defaults[field.key] = field.defaultValue;
    }
    return defaults;
  }, [optionFields]);

  const optionValues = { ...optionDefaults, ...optionOverrides };

  function fail(caught: unknown) {
    const payload = toErrorPayload(caught);
    setError(payload);
    setErrorNonce((value) => value + 1);
    setState("error");
    setStatusMessage("");
  }

  useEffect(() => {
    if ((analysis || uploads.length) && resultsRef.current) {
      resultsRef.current.focus();
    }
  }, [analysis, uploads.length]);

  async function runAnalyze(targetUrl: string) {
    setState("analyzing");
    setStatusMessage(copy.widget.analyzing);
    setError(null);
    setAnalysis(null);
    try {
      const result = await analyzeUrl(targetUrl.trim());
      setAnalysis(result);
      setState("ready");
      setStatusMessage("");
      if (result.status !== "ok") {
        return;
      }
      if (preselectedTool && result.tools.includes(preselectedTool)) {
        setSelectedTool(preselectedTool);
      } else if (result.tools[0]) {
        setSelectedTool(result.tools[0]);
      }
    } catch (caught) {
      fail(caught);
    }
  }

  useEffect(() => {
    if (redirectOnSubmit || autoStarted.current || (!initialUrl && !initialUploadId)) {
      return;
    }
    autoStarted.current = true;
    let cancelled = false;
    setState("analyzing");
    setStatusMessage(copy.widget.analyzing);
    void (async () => {
      try {
        if (initialUrl) {
          const result = await analyzeUrl(initialUrl.trim());
          if (cancelled) {
            return;
          }
          setAnalysis(result);
          setState("ready");
          setStatusMessage("");
          if (result.status === "ok") {
            if (preselectedTool && result.tools.includes(preselectedTool)) {
              setSelectedTool(preselectedTool);
            } else if (result.tools[0]) {
              setSelectedTool(result.tools[0]);
            }
          }
        } else if (initialUploadId) {
          const record = await getUpload(initialUploadId);
          if (cancelled) {
            return;
          }
          setUploads([record]);
          setState("ready");
          setStatusMessage("");
          if (preselectedTool && record.tools.includes(preselectedTool)) {
            setSelectedTool(preselectedTool);
          } else if (record.tools[0]) {
            setSelectedTool(record.tools[0]);
          }
        }
      } catch (caught) {
        if (!cancelled) {
          fail(caught);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [initialUrl, initialUploadId, redirectOnSubmit, preselectedTool]);

  async function uploadSelected(): Promise<UploadView[]> {
    await assertUploadSize(files);
    setState("uploading");
    setStatusMessage(copy.widget.uploadProgress);
    const records: UploadView[] = [];
    for (const file of files) {
      const started = performance.now();
      setUploadMeter({ percent: null, bytesPerSecond: null, name: file.name });
      const record = await uploadFile(file, (percent) => {
        // Speed from real bytes sent (the browser's own upload events), not an estimate.
        const seconds = (performance.now() - started) / 1000;
        const sent = (percent / 100) * file.size;
        setUploadMeter({
          percent,
          bytesPerSecond: seconds > 0.25 ? sent / seconds : null,
          name: file.name,
        });
      });
      records.push(record);
    }
    setUploads(records);
    setUploadMeter(null);
    return records;
  }

  async function onPrimarySubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);

    if (textOnly) {
      if (redirectOnSubmit) {
        router.push(`/tools/${preselectedTool}`);
        return;
      }
      setState("ready");
      setSelectedTool(preselectedTool ?? "qr-generator");
      return;
    }

    if (files.length > 0) {
      if (redirectOnSubmit) {
        try {
          const records = await uploadSelected();
          const first = records[0];
          const params = new URLSearchParams();
          params.set("upload", first.id);
          if (preselectedTool) {
            params.set("tool", preselectedTool);
          }
          router.push(`/analyze?${params.toString()}`);
        } catch (caught) {
          fail(caught);
        }
        return;
      }
      try {
        const records = await uploadSelected();
        setState("ready");
        setStatusMessage("");
        const tools = records[0]?.tools ?? [];
        if (preselectedTool && tools.includes(preselectedTool)) {
          setSelectedTool(preselectedTool);
        } else if (tools[0]) {
          setSelectedTool(tools[0]);
        }
      } catch (caught) {
        fail(caught);
      }
      return;
    }

    if (!url.trim()) {
      setError({
        code: "VALIDATION_ERROR",
        message: uploadsOnly ? "Choose a file first." : "Enter a URL or choose a file.",
        retryable: false,
      });
      setErrorNonce((value) => value + 1);
      setState("error");
      return;
    }

    if (redirectOnSubmit) {
      setState("analyzing");
      const params = new URLSearchParams({ url: url.trim() });
      if (preselectedTool) {
        params.set("tool", preselectedTool);
      }
      router.push(`/analyze?${params.toString()}`);
      return;
    }

    await runAnalyze(url);
  }

  async function onStart() {
    setError(null);
    const toolId = selectedTool || preselectedTool;
    if (!toolId) {
      return;
    }
    try {
      setState("running");
      setJob(null);
      setStatusMessage(copy.widget.running);
      const created = await createJob({
        tool: toolId,
        input: buildInput(toolId),
        options: collectOptions(optionFields, optionValues),
      });
      setJob(created);
      await pollJob(created.id);
    } catch (caught) {
      fail(caught);
    }
  }

  function buildInput(toolId: string) {
    const tool = getCatalogueTool(toolId);
    const kinds = tool?.inputs ?? ["url"];
    if (kinds.includes("text") && (textOnly || text.trim())) {
      return { kind: "text" as const, text };
    }
    if (uploads.length > 1 && kinds.includes("uploads")) {
      return { kind: "uploads" as const, upload_ids: uploads.map((item) => item.id) };
    }
    if (uploads.length === 1 && (kinds.includes("upload") || kinds.includes("uploads"))) {
      return kinds.includes("upload")
        ? { kind: "upload" as const, upload_id: uploads[0].id }
        : { kind: "uploads" as const, upload_ids: [uploads[0].id] };
    }
    return { kind: "url" as const, url: analysis?.normalized_url || url.trim() };
  }

  async function pollJob(id: string) {
    let current = await getJob(id);
    setJob(current);
    while (!isTerminalStatus(current.status)) {
      await wait(1000);
      current = await getJob(id);
      setJob(current);
      const phase =
        current.progress?.message || phaseLabel(current.progress?.phase || current.status);
      setStatusMessage(phase);
    }
    if (current.status === "COMPLETED") {
      router.push(`/r/${current.id}`);
      return;
    }
    setState("error");
    setErrorNonce((value) => value + 1);
    setError(
      current.error ?? {
        code: current.status,
        message:
          current.status === "CANCELLED"
            ? copy.result.cancelled
            : current.status === "EXPIRED"
              ? copy.result.expired
              : copy.result.failed,
        retryable: false,
      },
    );
  }

  async function onCancel() {
    if (!job) {
      return;
    }
    try {
      const next = await cancelJob(job.id);
      setJob(next);
      setState("error");
      setError({
        code: "JOB_CANCELLED",
        message: copy.result.cancelled,
        retryable: false,
      });
    } catch (caught) {
      fail(caught);
    }
  }

  async function onPaste() {
    try {
      const value = (await navigator.clipboard.readText()).trim();
      if (value) {
        setUrl(value);
        setJustPasted(true);
      }
    } catch {
      /* Permission refused: the field still accepts Ctrl/Cmd+V. */
    }
    urlRef.current?.focus();
  }

  const busy = state === "analyzing" || state === "uploading" || state === "running";
  const showOperations = !blocked && (analysis || uploads.length > 0 || textOnly);
  const startEnabled = Boolean(
    selectedTool && !blocked && (textOnly ? text.trim() : uploads.length > 0 || analysis),
  );
  const host = hostOf(url);
  const selectedCatalogue = getCatalogueTool(selectedTool || preselectedTool || "");
  const hero = layout === "hero";
  const inputSize = uploads[0]?.size_bytes ?? analysis?.size_bytes ?? null;
  const fromLabel = uploads[0]
    ? extensionOf(uploads[0].filename)
    : analysis
      ? typeLabel(analysis.resource_type)
      : undefined;
  const outputOption = optionValues.format ?? optionValues.target ?? optionValues.image_format;
  const outputLabel =
    typeof outputOption === "string" && /^[a-z0-9]{2,5}$/i.test(outputOption)
      ? outputOption.toUpperCase()
      : undefined;
  const fileInvalid = Boolean(error && error.code === "FILE_TOO_LARGE");

  const panel = (
    <section
      aria-label={catalogue?.name ?? "Workspace"}
      className={cn(
        "surface-raised workspace-glow relative overflow-hidden",
        hero ? "rounded-3xl" : "rounded-3xl",
      )}
    >
      <div className="border-border bg-background-alt/60 flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5 sm:px-6">
        <div className="flex min-w-0 items-center gap-2.5">
          {catalogue ? (
            <CategoryIcon category={catalogue.category} size="sm" />
          ) : (
            <span aria-hidden="true" className="flex gap-1.5">
              <span className="bg-border-strong size-2.5 rounded-full" />
              <span className="bg-border-strong size-2.5 rounded-full" />
              <span className="bg-accent size-2.5 rounded-full" />
            </span>
          )}
          <p className="truncate text-sm font-semibold">{catalogue?.name ?? "New workspace"}</p>
        </div>
        <p className="text-muted-foreground flex items-center gap-2 text-xs font-medium">
          <span
            aria-hidden="true"
            className="text-success ping-dot inline-block size-2 rounded-full bg-current"
          />
          No account · Files auto-delete
        </p>
      </div>

      <form onSubmit={onPrimarySubmit} className="space-y-4 p-4 sm:p-6">
        {textOnly ? (
          <div>
            <Label htmlFor="qr-text">{copy.widget.textLabel}</Label>
            <Textarea
              id="qr-text"
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={copy.widget.textPlaceholder}
              maxLength={2000}
            />
          </div>
        ) : (
          <>
            {!uploadsOnly ? (
              <div>
                <Label
                  htmlFor="source-url"
                  className={hero ? "sr-only sm:not-sr-only sm:mb-2" : ""}
                >
                  {urlOnly ? "Paste a public URL" : copy.widget.label}
                </Label>
                <div
                  className={cn(
                    "bg-card border-input/50 group/url shadow-xs flex flex-wrap items-center gap-2 rounded-2xl border p-1.5 transition-[border-color,box-shadow] duration-200 sm:flex-nowrap",
                    "focus-within:border-accent focus-within:ring-accent/15 hover:border-input focus-within:ring-4",
                    justPasted && "border-accent ring-accent/20 ring-4",
                  )}
                >
                  <span
                    aria-hidden="true"
                    className={cn(
                      "text-muted-foreground group-focus-within/url:text-accent grid size-10 shrink-0 place-items-center transition-colors",
                      host && "text-accent",
                    )}
                  >
                    {host ? <Globe className="animate-pop size-5" /> : <Link2 className="size-5" />}
                  </span>
                  <Input
                    ref={urlRef}
                    id="source-url"
                    name="url"
                    type="url"
                    inputMode="url"
                    autoComplete="url"
                    placeholder={copy.widget.urlPlaceholder}
                    value={url}
                    onChange={(event) => setUrl(event.target.value)}
                    onPaste={() => setJustPasted(true)}
                    disabled={busy}
                    className={cn(
                      "min-h-11 min-w-0 flex-1 basis-0 border-0 bg-transparent px-1 shadow-none hover:border-0 focus-visible:ring-0",
                      justPasted && "animate-fade-in",
                    )}
                  />
                  {canPaste && !url ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => void onPaste()}
                      disabled={busy}
                      aria-label="Paste from clipboard"
                      className="text-muted-foreground hover:text-foreground min-w-10 px-2.5 sm:px-3.5"
                    >
                      <ClipboardPaste className="transition-transform duration-200 group-hover/button:-rotate-6 group-hover/button:scale-110" />
                      <span className="hidden sm:inline">Paste</span>
                    </Button>
                  ) : null}
                  {!uploadsOnly ? (
                    <Button
                      type="submit"
                      size="lg"
                      className="w-full min-w-36 sm:w-auto"
                      disabled={busy}
                    >
                      {state === "analyzing" ? (
                        <>
                          <Spinner />
                          {copy.widget.analyzing}
                        </>
                      ) : (
                        <>
                          {copy.widget.analyze}
                          <ArrowRight className="transition-transform duration-200 group-hover/button:translate-x-0.5" />
                        </>
                      )}
                    </Button>
                  ) : null}
                </div>
                <div className="mt-2.5 flex min-h-7 flex-wrap items-center gap-2 text-xs">
                  {host ? (
                    <p
                      key={host}
                      className="animate-fade-in text-muted-foreground flex items-center gap-1.5"
                    >
                      <span className="bg-accent-soft text-accent-soft-foreground rounded-md px-2 py-0.5 font-semibold">
                        {host}
                      </span>
                      {analysis?.normalized_url === url.trim() || state === "analyzing"
                        ? "This is the link being analyzed."
                        : "Press Analyze to see what this source allows."}
                    </p>
                  ) : (
                    <>
                      <span className="text-muted-foreground">Works with public</span>
                      {FORMAT_HINTS.map((hint) => (
                        <span
                          key={hint}
                          className="bg-muted text-muted-foreground rounded-md px-2 py-0.5 font-medium"
                        >
                          {hint}
                        </span>
                      ))}
                    </>
                  )}
                </div>
              </div>
            ) : null}
            {!urlOnly ? (
              <>
                {!uploadsOnly ? (
                  <div
                    className="text-muted-foreground flex items-center gap-3 text-xs font-semibold uppercase tracking-wider"
                    aria-hidden="true"
                  >
                    <span className="bg-border h-px flex-1" />
                    or
                    <span className="bg-border h-px flex-1" />
                  </div>
                ) : null}
                <FileDropzone
                  key={`drop-${errorNonce}`}
                  files={files}
                  multiple={multiUpload}
                  disabled={busy}
                  invalid={fileInvalid}
                  compact={hero || !uploadsOnly}
                  onChange={setFiles}
                />
              </>
            ) : null}
          </>
        )}

        {textOnly || uploadsOnly || state === "running" ? (
          <div className="flex flex-wrap gap-3">
            {textOnly ? (
              <Button
                type="button"
                size="lg"
                onClick={() => void onStart()}
                disabled={!text.trim() || state === "running"}
              >
                {state === "running" ? (
                  <>
                    <Spinner />
                    {copy.widget.running}
                  </>
                ) : (
                  copy.widget.run
                )}
              </Button>
            ) : uploadsOnly ? (
              <Button type="submit" size="lg" className="min-w-40" disabled={busy}>
                {state === "uploading" ? (
                  <>
                    <Spinner />
                    {copy.widget.uploadProgress}
                  </>
                ) : (
                  copy.widget.analyze
                )}
              </Button>
            ) : null}
          </div>
        ) : null}
      </form>

      {state === "analyzing" ? <AnalyzingStrip host={host} /> : null}

      {state === "uploading" ? (
        <div className="border-border animate-fade-in border-t px-4 py-4 sm:px-6">
          <Progress
            value={uploadMeter?.percent}
            label={`${copy.widget.uploadProgress}${uploadMeter?.name ? ` ${uploadMeter.name}` : ""}`}
            detail={
              uploadMeter?.bytesPerSecond
                ? `${formatBytes(uploadMeter.bytesPerSecond)}/s`
                : "Sending to the server over a streaming upload"
            }
          />
        </div>
      ) : null}
    </section>
  );

  const flow = (
    <div className="min-w-0 space-y-5">
      {panel}

      {/* Progress only. Errors are announced once, by the visible role="alert" below;
          repeating them here made screen readers read every rejection twice. */}
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {error ? "" : statusMessage}
      </div>

      {preselectedTool && runtimeUnavailable.has(preselectedTool) ? (
        <StatusPanel
          role="status"
          error={{
            code: "TOOL_UNAVAILABLE",
            message: copy.widget.toolUnavailable,
            retryable: false,
          }}
        />
      ) : null}

      {error ? (
        <StatusPanel
          key={errorNonce}
          error={error}
          onRetry={() => {
            setError(null);
            setState("idle");
          }}
          retryLabel={copy.widget.retry}
        />
      ) : null}

      {analysis || uploads.length > 0 ? (
        <div className="space-y-6">
          <h2 ref={resultsRef} tabIndex={-1} className="sr-only">
            {copy.widget.resultsHeading}
          </h2>
          <AnalysisResult analysis={analysis} upload={uploads[0]} />
        </div>
      ) : null}

      {blocked && analysis?.reason ? (
        <div className="animate-fade-up space-y-3 [--ad-delay:120ms]">
          <p className="text-muted-foreground px-1 text-xs font-bold uppercase tracking-[0.16em]">
            {copy.widget.cannotProcess}
          </p>
          <StatusPanel role="status" error={analysis.reason} />
          {analysis.platform?.toLowerCase() === "youtube" ? <YouTubeHelp /> : null}
          <Alternatives currentId={preselectedTool} />
        </div>
      ) : null}

      {showOperations && !blocked ? (
        <div className="surface animate-fade-up space-y-6 rounded-2xl p-4 [--ad-delay:160ms] sm:p-6">
          <fieldset>
            <legend className="font-display mb-1 text-lg font-bold">
              {copy.widget.availableOperations}
            </legend>
            <p className="text-muted-foreground mb-4 text-sm">
              {availableToolIds.length > 1
                ? `The server offered ${availableToolIds.length} tools for this source. Pick one.`
                : "Only tools that work with this source are shown."}
            </p>
            {availableToolIds.length === 0 && !textOnly ? (
              <p className="text-muted-foreground text-sm">{copy.widget.noTools}</p>
            ) : (
              <ul className="grid gap-2.5 sm:grid-cols-2">
                {(textOnly ? [selectedTool] : availableToolIds).map((id, index) => {
                  const item = getCatalogueTool(id);
                  const selected = selectedTool === id;
                  return (
                    <li key={id} className="animate-fade-up" style={{ ["--i" as string]: index }}>
                      <label
                        className={cn(
                          "group relative flex min-h-11 cursor-pointer items-start gap-3 rounded-xl border px-3.5 py-3 transition-[border-color,background-color,box-shadow,transform] duration-200",
                          "has-[input:focus-visible]:ring-ring has-[input:focus-visible]:ring-2 has-[input:focus-visible]:ring-offset-2",
                          selected
                            ? "border-accent bg-selected-gradient shadow-sm"
                            : "border-border bg-card hover:border-border-strong hover:-translate-y-0.5 hover:shadow-sm",
                        )}
                      >
                        <input
                          type="radio"
                          name="tool"
                          className="peer sr-only"
                          checked={selected}
                          onChange={() => {
                            setSelectedTool(id);
                            setOptionOverrides({});
                          }}
                        />
                        {item ? (
                          <CategoryIcon
                            category={item.category}
                            size="sm"
                            className="group-hover:scale-105"
                          />
                        ) : null}
                        <span className="min-w-0 flex-1">
                          <span className="block font-semibold">{item?.name ?? id}</span>
                          <span className="text-muted-foreground block text-sm">{item?.short}</span>
                        </span>
                        <span
                          aria-hidden="true"
                          className={cn(
                            "mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border transition-colors",
                            selected
                              ? "bg-accent border-accent text-accent-foreground"
                              : "border-border-strong bg-card",
                          )}
                        >
                          {selected && state === "running" ? (
                            <Spinner className="size-3" />
                          ) : selected ? (
                            <Check className="animate-pop size-3" strokeWidth={3.5} />
                          ) : null}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </fieldset>
          <ToolOptions
            fields={optionFields}
            values={optionValues}
            onChange={(key, value) =>
              setOptionOverrides((current) => ({ ...current, [key]: value }))
            }
          />
          {!textOnly ? (
            <div className="border-border flex flex-wrap items-center gap-4 border-t pt-5">
              <Button
                type="button"
                size="lg"
                className="min-w-40"
                onClick={() => void onStart()}
                disabled={!startEnabled || state === "running"}
              >
                {state === "running" ? (
                  <>
                    <Spinner />
                    {copy.widget.running}
                  </>
                ) : (
                  <>
                    {copy.widget.run}
                    <ArrowRight className="transition-transform duration-200 group-hover/button:translate-x-0.5" />
                  </>
                )}
              </Button>
              {selectedCatalogue ? (
                <p className="text-muted-foreground text-sm">
                  Runs{" "}
                  <span className="text-foreground font-semibold">{selectedCatalogue.name}</span>
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
      {state === "running" ? (
        <div ref={processingRef} className="scroll-mt-28">
          <ProcessingCard
            job={job}
            tool={selectedCatalogue}
            fromUpload={uploads.length > 0}
            fetchesSource={buildInputKind() === "url"}
            fromLabel={fromLabel}
            outputLabel={outputLabel}
            inputSize={inputSize}
            onCancel={job ? () => void onCancel() : undefined}
          />
        </div>
      ) : null}
    </div>
  );

  function buildInputKind() {
    if (textOnly) return "text";
    if (uploads.length > 0) return "upload";
    return "url";
  }

  if (hero) {
    return flow;
  }

  const journey = journeyStages({
    textOnly,
    hasInput: Boolean(url.trim() || files.length || uploads.length || analysis || text.trim()),
    state,
    analysed: Boolean(analysis || uploads.length),
    blocked,
    showOperations: Boolean(showOperations),
    hasJob: Boolean(job),
    jobPhase: job?.progress?.phase,
  });

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_20rem] 2xl:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-w-0 space-y-5">
        {flow}
        {aside ? <div className="grid items-start gap-5 md:grid-cols-2">{aside}</div> : null}
      </div>
      <aside className="space-y-5 xl:sticky xl:top-24" aria-label="Progress and details">
        <div className="surface rounded-2xl p-5">
          <p className="text-muted-foreground mb-4 text-xs font-bold uppercase tracking-[0.16em]">
            Your progress
          </p>
          <StageList stages={journey} />
        </div>
        <LimitsCard />
      </aside>
    </div>
  );
}

function journeyStages({
  textOnly,
  hasInput,
  state,
  analysed,
  blocked,
  showOperations,
  hasJob,
  jobPhase,
}: {
  textOnly: boolean;
  hasInput: boolean;
  state: LiveState;
  analysed: boolean;
  blocked: boolean;
  showOperations: boolean;
  hasJob: boolean;
  jobPhase?: string;
}): Stage[] {
  const running = state === "running";
  const failedJob = state === "error" && hasJob;
  const stages: Stage[] = [
    {
      id: "input",
      label: textOnly ? "Enter your text" : "Add a link or file",
      state: hasInput || analysed ? "done" : "waiting",
    },
  ];
  if (!textOnly) {
    stages.push({
      id: "analyze",
      label: state === "uploading" ? "Uploading" : "Analyze",
      detail: blocked ? "This source can't be processed" : undefined,
      state:
        state === "analyzing" || state === "uploading"
          ? "active"
          : blocked || (state === "error" && !analysed && !hasJob)
            ? "error"
            : analysed
              ? "done"
              : hasInput
                ? "waiting"
                : "pending",
    });
    stages.push({
      id: "choose",
      label: "Choose a tool",
      state: hasJob || running ? "done" : showOperations && analysed ? "waiting" : "pending",
    });
  }
  stages.push({
    id: "process",
    label: "Process",
    detail: running && jobPhase ? phaseLabel(jobPhase) : undefined,
    state: running ? "active" : failedJob ? "error" : textOnly && hasInput ? "waiting" : "pending",
  });
  stages.push({ id: "download", label: "Download", state: "pending" });
  return stages;
}

function AnalyzingStrip({ host }: { host: string | null }) {
  return (
    <div className="border-border animate-fade-in relative overflow-hidden border-t px-4 py-4 sm:px-6">
      <span
        aria-hidden="true"
        className="scan-line via-accent/10 absolute inset-y-0 left-0 w-full bg-gradient-to-r from-transparent to-transparent"
      />
      <div className="relative flex items-center gap-3">
        <span className="bg-accent-soft text-accent grid size-9 place-items-center rounded-xl">
          <Spinner />
        </span>
        <div>
          <p className="text-sm font-semibold">
            Analyzing {host ? <span className="text-accent">{host}</span> : "your link"}
          </p>
          <p className="text-muted-foreground text-xs">
            Asking the source what it publicly offers. This usually takes a few seconds.
          </p>
        </div>
      </div>
    </div>
  );
}

function LimitsCard() {
  const [limits, setLimits] = useState<Limits | null>(null);
  useEffect(() => {
    let cancelled = false;
    void getLimits().then((value) => {
      if (!cancelled) setLimits(value);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const items = [
    {
      icon: Lock,
      text: "No account. Links are not stored in full in logs.",
    },
    {
      icon: Sparkles,
      text: limits
        ? `Results delete themselves after ${Math.round(limits.result_ttl_seconds / 60)} minutes.`
        : "Results delete themselves automatically.",
    },
    ...(limits
      ? [{ icon: Check, text: `Uploads up to ${formatBytes(limits.max_upload_bytes)} per file.` }]
      : []),
  ];

  return (
    <div className="surface rounded-2xl p-5">
      <p className="text-muted-foreground mb-3 text-xs font-bold uppercase tracking-[0.16em]">
        Privacy & limits
      </p>
      <ul className="space-y-2.5 text-sm">
        {items.map((item) => (
          <li key={item.text} className="flex gap-2.5">
            <item.icon className="text-success mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{item.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

const SELF_HOST_URL =
  "https://github.com/sandeepbollavaram/anything-download#run-it-on-your-own-computer";

/** Honest guidance when YouTube refuses this server; never a workaround for its bot check. */
function YouTubeHelp() {
  return (
    <div className="surface rounded-2xl p-5">
      <h3 className="font-display font-bold">{copy.widget.youtubeTitle}</h3>
      <p className="text-muted-foreground mt-1 text-sm">{copy.widget.youtubeBody}</p>
      <ul className="mt-3 space-y-2 text-sm">
        {copy.widget.youtubeTips.map((tip) => (
          <li key={tip} className="flex gap-2.5">
            <Check className="text-success mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <span>{tip}</span>
          </li>
        ))}
      </ul>
      <a
        href={SELF_HOST_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="text-link mt-3 inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold"
      >
        <span className="underline-grow">{copy.widget.youtubeSelfHost}</span>
        <ArrowRight className="size-4" aria-hidden="true" />
      </a>
    </div>
  );
}

function Alternatives({ currentId }: { currentId?: string }) {
  const tools = toolsNotNeedingSource(currentId);
  if (tools.length === 0) {
    return null;
  }
  return (
    <div className="surface rounded-2xl p-5">
      <h3 className="font-display font-bold">{copy.widget.alternativesHeading}</h3>
      <p className="text-muted-foreground mt-1 text-sm">{copy.widget.alternativesLead}</p>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {tools.map((tool, index) => (
          <li key={tool.id} className="animate-fade-up" style={{ ["--i" as string]: index }}>
            <Link
              href={`/tools/${tool.id}`}
              className="hover:bg-muted group flex min-h-11 items-center gap-3 rounded-xl px-2 py-1.5"
            >
              <CategoryIcon category={tool.category} size="sm" />
              <span className="flex-1 font-semibold">{tool.name}</span>
              <ArrowRight
                className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5"
                aria-hidden="true"
              />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function hostOf(value: string) {
  const trimmed = value.trim();
  if (!/^https?:\/\//i.test(trimmed)) {
    return null;
  }
  try {
    return new URL(trimmed).hostname.replace(/^www\./, "") || null;
  } catch {
    return null;
  }
}

function extensionOf(filename: string) {
  const ext = filename.includes(".") ? filename.split(".").pop() : null;
  return ext && ext.length <= 5 ? ext.toUpperCase() : undefined;
}

function typeLabel(type: string) {
  return type === "UNKNOWN" ? undefined : type.charAt(0) + type.slice(1).toLowerCase();
}

function wait(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}
