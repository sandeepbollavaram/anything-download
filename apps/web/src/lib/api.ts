import { apiPath } from "@/lib/env";
import { formatBytes } from "@/lib/format";

export type ResourceType =
  "VIDEO" | "IMAGE" | "AUDIO" | "PDF" | "DOCUMENT" | "WEBPAGE" | "ARCHIVE" | "UNKNOWN";

export type SourceKind = "direct" | "webpage" | "platform";
export type AnalysisStatus = "ok" | "unsupported" | "restricted";

export type JobStatus = "QUEUED" | "RUNNING" | "COMPLETED" | "FAILED" | "EXPIRED" | "CANCELLED";

export type InputKind = "url" | "upload" | "uploads" | "text";

export type ErrorPayload = {
  code: string;
  message: string;
  retryable: boolean;
  details?: Record<string, unknown>;
  /** Seconds from the server's Retry-After header, when it sent one. */
  retryAfterSeconds?: number;
};

export type ApiErrorBody = {
  error: ErrorPayload;
};

export type MediaFormat = {
  id: string;
  label: string;
  kind: "video" | "audio" | "video+audio" | "image" | "file";
  ext?: string | null;
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  filesize?: number | null;
  filesize_is_estimate?: boolean;
  vcodec?: string | null;
  acodec?: string | null;
  bitrate_kbps?: number | null;
};

export type URLAnalysis = {
  normalized_url: string;
  final_url?: string | null;
  source_kind: SourceKind;
  resource_type: ResourceType;
  platform?: string | null;
  mime_type?: string | null;
  title?: string | null;
  description?: string | null;
  thumbnail?: string | null;
  duration_seconds?: number | null;
  size_bytes?: number | null;
  filename?: string | null;
  width?: number | null;
  height?: number | null;
  capabilities: string[];
  tools: string[];
  formats: MediaFormat[];
  restrictions: string[];
  warnings: string[];
  resource_counts: Record<string, number>;
  status: AnalysisStatus;
  reason?: ErrorPayload | null;
};

export type JobProgress = {
  phase: string;
  percent?: number | null;
  message?: string | null;
};

export type ResultFile = {
  filename: string;
  mime_type: string;
  size_bytes: number;
  resource_type: ResourceType;
};

export type JobResult = {
  file?: ResultFile | null;
  data?: Record<string, unknown> | null;
  notes?: string[];
};

export type JobView = {
  id: string;
  tool: string;
  status: JobStatus;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  expires_at?: string | null;
  progress?: JobProgress | null;
  result?: JobResult | null;
  error?: ErrorPayload | null;
  result_url?: string | null;
};

export type JobInput = {
  kind: InputKind;
  url?: string;
  upload_id?: string;
  upload_ids?: string[];
  text?: string;
};

export type UploadView = {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  resource_type: ResourceType;
  expires_at: string;
  tools: string[];
};

export type ToolView = {
  id: string;
  category: string;
  capability: string;
  inputs: InputKind[];
  accepts: ResourceType[];
  requires: string[];
  available: boolean;
  missing_requirements: string[];
  output: string;
  options_schema: Record<string, unknown>;
  seo_page: boolean;
};

export type ToolsResponse = {
  tools: ToolView[];
};

export type HealthResponse = {
  status: string;
  version: string;
};

export class ApiError extends Error {
  readonly code: string;
  readonly retryable: boolean;
  readonly details?: Record<string, unknown>;
  readonly status: number;
  readonly retryAfterSeconds?: number;

  constructor(payload: ErrorPayload, status: number, retryAfterSeconds?: number) {
    super(payload.message);
    this.name = "ApiError";
    this.code = payload.code;
    this.retryable = payload.retryable;
    this.details = payload.details;
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

function parseRetryAfter(value: string | null): number | undefined {
  if (!value) {
    return undefined;
  }
  const seconds = Number(value);
  return Number.isFinite(seconds) && seconds > 0 ? Math.ceil(seconds) : undefined;
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (!value || typeof value !== "object") {
    return false;
  }
  const error = (value as ApiErrorBody).error;
  return Boolean(error && typeof error.code === "string" && typeof error.message === "string");
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      throw new ApiError(
        {
          code: response.ok ? "INTERNAL_ERROR" : "SERVICE_UNAVAILABLE",
          message: response.ok
            ? "The server returned a response that could not be read."
            : "The API is not reachable.",
          retryable: true,
        },
        response.status || 503,
      );
    }
  }
  if (!response.ok) {
    if (isApiErrorBody(data)) {
      throw new ApiError(
        data.error,
        response.status,
        parseRetryAfter(response.headers.get("Retry-After")),
      );
    }
    throw new ApiError(
      {
        code: "INTERNAL_ERROR",
        message: response.statusText || "The request failed.",
        retryable: response.status >= 500,
      },
      response.status,
    );
  }
  return data as T;
}

async function request<T>(
  path: string,
  init: RequestInit & { parseJson?: boolean } = {},
): Promise<T> {
  const { parseJson = true, headers, ...rest } = init;
  const response = await fetch(apiPath(path), {
    ...rest,
    headers: {
      Accept: "application/json",
      ...headers,
    },
  });
  if (!parseJson) {
    if (!response.ok) {
      await parseResponse(response);
    }
    return response as T;
  }
  return parseResponse<T>(response);
}

export function analyzeUrl(url: string): Promise<URLAnalysis> {
  return request<URLAnalysis>("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
}

export function createJob(body: {
  tool: string;
  input: JobInput;
  options?: Record<string, unknown>;
}): Promise<JobView> {
  return request<JobView>("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tool: body.tool,
      input: body.input,
      options: body.options ?? {},
    }),
  });
}

export function getJob(id: string): Promise<JobView> {
  return request<JobView>(`/jobs/${encodeURIComponent(id)}`);
}

export function cancelJob(id: string): Promise<JobView> {
  return request<JobView>(`/jobs/${encodeURIComponent(id)}/cancel`, { method: "POST" });
}

export function deleteJob(id: string): Promise<void> {
  return request<void>(`/jobs/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function getUpload(id: string): Promise<UploadView> {
  return request<UploadView>(`/uploads/${encodeURIComponent(id)}`);
}

export function deleteUpload(id: string): Promise<void> {
  return request<void>(`/uploads/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function listTools(init?: RequestInit): Promise<ToolsResponse> {
  return request<ToolsResponse>("/tools", init);
}

export function getTool(id: string): Promise<ToolView> {
  return request<ToolView>(`/tools/${encodeURIComponent(id)}`);
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export type Limits = {
  max_upload_bytes: number;
  max_file_bytes: number;
  max_url_length: number;
  max_text_chars: number;
  max_files_per_job: number;
  result_ttl_seconds: number;
  upload_ttl_seconds: number;
};

let limitsRequest: Promise<Limits | null> | null = null;

/** Public limits, fetched once per page. Resolves to null if they cannot be loaded. */
export function getLimits(): Promise<Limits | null> {
  if (!limitsRequest) {
    limitsRequest = request<Limits>("/limits").catch(() => {
      limitsRequest = null; // try again next time rather than caching the failure
      return null;
    });
  }
  return limitsRequest;
}

/**
 * Refuse a file that is over the upload limit before sending any of it. Without this,
 * the API rejects it from the declared size, but a browser that is still sending can
 * stall until its own timeout instead of showing the error. The API stays authoritative:
 * if the limits cannot be loaded, the upload proceeds and the server decides.
 */
export async function assertUploadSize(files: readonly File[]): Promise<void> {
  const limits = await getLimits();
  if (!limits) {
    return;
  }
  const tooLarge = files.find((file) => file.size > limits.max_upload_bytes);
  if (tooLarge) {
    throw new ApiError(
      {
        code: "FILE_TOO_LARGE",
        message: `${tooLarge.name} is ${formatBytes(tooLarge.size)}. Uploads are limited to ${formatBytes(limits.max_upload_bytes)}.`,
        retryable: false,
      },
      413,
    );
  }
}

export function jobResultUrl(jobId: string): string {
  return apiPath(`/jobs/${encodeURIComponent(jobId)}/result`);
}

export type UploadProgressHandler = (percent: number) => void;

export function uploadFile(file: File, onProgress?: UploadProgressHandler): Promise<UploadView> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", apiPath("/uploads"));
    xhr.responseType = "text";
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.setRequestHeader("X-File-Name", encodeURIComponent(file.name));
    if (file.type) {
      xhr.setRequestHeader("X-File-Type", file.type);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.min(100, (event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      try {
        let data: unknown = null;
        try {
          data = xhr.responseText ? JSON.parse(xhr.responseText) : null;
        } catch {
          // A proxy or gateway error page is not JSON. Surface a readable error
          // instead of the parser's "Unexpected token" message.
          reject(
            new ApiError(
              {
                code:
                  xhr.status >= 200 && xhr.status < 300 ? "INTERNAL_ERROR" : "SERVICE_UNAVAILABLE",
                message: "The upload failed before the server could respond. Please try again.",
                retryable: true,
              },
              xhr.status || 503,
            ),
          );
          return;
        }
        if (xhr.status < 200 || xhr.status >= 300) {
          if (isApiErrorBody(data)) {
            reject(
              new ApiError(
                data.error,
                xhr.status,
                parseRetryAfter(xhr.getResponseHeader("Retry-After")),
              ),
            );
            return;
          }
          reject(
            new ApiError(
              {
                code: "INTERNAL_ERROR",
                message: "The upload failed.",
                retryable: xhr.status >= 500,
              },
              xhr.status,
            ),
          );
          return;
        }
        resolve(data as UploadView);
      } catch (error) {
        reject(error);
      }
    };
    xhr.onerror = () => {
      reject(
        new ApiError(
          {
            code: "SERVICE_UNAVAILABLE",
            message: "The upload could not reach the server.",
            retryable: true,
          },
          0,
        ),
      );
    };
    xhr.onabort = () => {
      reject(
        new ApiError(
          {
            code: "JOB_CANCELLED",
            message: "The upload was cancelled.",
            retryable: false,
          },
          0,
        ),
      );
    };
    xhr.send(file);
  });
}

export function isTerminalStatus(status: JobStatus): boolean {
  return (
    status === "COMPLETED" || status === "FAILED" || status === "EXPIRED" || status === "CANCELLED"
  );
}

export function toErrorPayload(error: unknown): ErrorPayload {
  if (error instanceof ApiError) {
    return {
      code: error.code,
      message: error.message,
      retryable: error.retryable,
      details: error.details,
      retryAfterSeconds: error.retryAfterSeconds,
    };
  }
  if (error instanceof Error) {
    return {
      code: "INTERNAL_ERROR",
      message: error.message,
      retryable: true,
    };
  }
  return {
    code: "INTERNAL_ERROR",
    message: "Something went wrong.",
    retryable: true,
  };
}
