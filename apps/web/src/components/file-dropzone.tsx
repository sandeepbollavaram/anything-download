"use client";

import {
  File as FileIcon,
  FileText,
  Image as ImageIcon,
  Music,
  UploadCloud,
  Video,
  X,
} from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { copy } from "@/lib/copy";
import { formatBytes } from "@/lib/format";

export function FileDropzone({
  files,
  multiple = false,
  accept,
  disabled,
  invalid = false,
  compact = false,
  onChange,
}: {
  files: File[];
  multiple?: boolean;
  accept?: string;
  disabled?: boolean;
  /** Plays a short shake and red outline, e.g. when the file was refused. */
  invalid?: boolean;
  compact?: boolean;
  onChange: (files: File[]) => void;
}) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragDepth, setDragDepth] = useState(0);
  const dragOver = dragDepth > 0;

  function addFiles(list: FileList | File[] | null) {
    if (!list) {
      return;
    }
    const next = Array.from(list);
    onChange(multiple ? [...files, ...next] : next.slice(0, 1));
  }

  return (
    <div className="space-y-3">
      <div
        onDragEnter={(event) => {
          event.preventDefault();
          setDragDepth((depth) => depth + 1);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragDepth((depth) => Math.max(0, depth - 1))}
        onDrop={(event) => {
          event.preventDefault();
          setDragDepth(0);
          if (!disabled) {
            addFiles(event.dataTransfer.files);
          }
        }}
        className={cn(
          "group/drop relative overflow-hidden rounded-2xl border-2 border-dashed transition-[border-color,background-color,transform] duration-200",
          "border-border-strong bg-background-alt/50 hover:border-input",
          dragOver && "border-accent bg-accent-soft scale-[1.01]",
          invalid && "animate-shake border-destructive",
          disabled && "opacity-60",
          compact
            ? "flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-3.5"
            : "px-4 py-8 text-center",
        )}
      >
        <span
          aria-hidden="true"
          className={cn(
            "bg-card text-accent grid shrink-0 place-items-center rounded-xl shadow-sm transition-transform duration-300 group-hover/drop:-translate-y-0.5",
            compact ? "size-10" : "mx-auto mb-3 size-12",
            dragOver && "-translate-y-1 scale-110",
          )}
        >
          <UploadCloud className={compact ? "size-5" : "size-6"} strokeWidth={2.2} />
        </span>
        <div className={cn(compact ? "min-w-0 flex-1 basis-[11rem]" : "")}>
          <p className="font-display text-sm font-bold">
            {dragOver ? "Release to add" : copy.widget.dropTitle}
          </p>
          <p className="text-muted-foreground text-sm">{copy.widget.dropHint}</p>
        </div>
        <div className={compact ? "" : "mt-4"}>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            className="sr-only"
            // The visible button below opens this input; one tab stop, one announcement.
            tabIndex={-1}
            aria-hidden="true"
            aria-label={multiple ? copy.widget.chooseFiles : copy.widget.chooseFile}
            multiple={multiple}
            accept={accept}
            disabled={disabled}
            onChange={(event) => {
              addFiles(event.target.files);
              event.target.value = "";
            }}
          />
          <Button
            type="button"
            variant="outline"
            size={compact ? "sm" : "default"}
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            {multiple ? copy.widget.chooseFiles : copy.widget.chooseFile}
          </Button>
        </div>
      </div>
      {files.length > 0 ? (
        <ul className="space-y-2" aria-label={copy.widget.selectedFile}>
          {files.map((file, index) => (
            <SelectedFile
              key={`${file.name}-${file.size}-${index}`}
              file={file}
              index={index}
              disabled={disabled}
              onRemove={() => onChange(files.filter((_, i) => i !== index))}
            />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function SelectedFile({
  file,
  index,
  disabled,
  onRemove,
}: {
  file: File;
  index: number;
  disabled?: boolean;
  onRemove: () => void;
}) {
  // Local preview only: the image never leaves the browser until the person presses Analyze.
  // A data: URL (allowed by the CSP's img-src) instead of blob:, so the policy stays as strict.
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  useEffect(() => {
    const previewable =
      file.type.startsWith("image/") &&
      file.type !== "image/svg+xml" &&
      file.size < 8 * 1024 * 1024;
    if (!previewable) {
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setPreviewUrl(typeof reader.result === "string" ? reader.result : null);
    reader.readAsDataURL(file);
    return () => reader.abort();
  }, [file]);

  const Icon = file.type.startsWith("video/")
    ? Video
    : file.type.startsWith("audio/")
      ? Music
      : file.type.startsWith("image/")
        ? ImageIcon
        : file.type === "application/pdf"
          ? FileText
          : FileIcon;
  const ext = file.name.includes(".") ? file.name.split(".").pop()?.toUpperCase() : null;

  return (
    <li
      className="bg-card border-border animate-fade-up shadow-xs flex items-center gap-3 rounded-xl border p-2 pr-1"
      style={{ ["--i" as string]: index }}
    >
      <span className="bg-muted text-muted-foreground relative grid size-11 shrink-0 place-items-center overflow-hidden rounded-lg">
        {previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={previewUrl} alt="" className="animate-scale-in size-full object-cover" />
        ) : (
          <Icon className="size-5" aria-hidden="true" />
        )}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold">{file.name}</span>
        <span className="text-muted-foreground block text-xs">
          {[ext, formatBytes(file.size)].filter(Boolean).join(" · ")}
        </span>
      </span>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        disabled={disabled}
        aria-label={`${copy.widget.removeFile}: ${file.name}`}
        onClick={onRemove}
      >
        <X />
      </Button>
    </li>
  );
}
