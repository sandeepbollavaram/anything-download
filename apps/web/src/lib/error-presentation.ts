import {
  AlertTriangle,
  Ban,
  CloudOff,
  FileWarning,
  Globe2,
  Hourglass,
  Lock,
  Radio,
  SearchX,
  ServerCrash,
  ShieldAlert,
  ShieldX,
  Timer,
  Unlink,
  WifiOff,
  type LucideIcon,
} from "lucide-react";

import type { ErrorPayload } from "@/lib/api";

export type ErrorTone = "danger" | "warning" | "neutral";

export type ErrorPresentation = {
  title: string;
  /** What the person can do next. The server's own message is always shown as well. */
  next: string;
  icon: LucideIcon;
  tone: ErrorTone;
};

const BY_CODE: Record<string, ErrorPresentation> = {
  SERVICE_UNAVAILABLE: {
    title: "Can't reach Anything Download.",
    next: "Check your connection, then try again.",
    icon: WifiOff,
    tone: "warning",
  },
  RATE_LIMITED: {
    title: "You're moving faster than the service can safely process.",
    next: "Take a short breather. You can try again when the timer ends.",
    icon: Timer,
    tone: "warning",
  },
  SOURCE_PRIVATE: {
    title: "This content requires access we don't have.",
    next: "Only public content can be processed. Try a public link or upload a file you own.",
    icon: Lock,
    tone: "neutral",
  },
  SOURCE_REQUIRES_AUTH: {
    title: "This content requires access we don't have.",
    next: "Only public content can be processed. Try a public link or upload a file you own.",
    icon: Lock,
    tone: "neutral",
  },
  SOURCE_DRM_PROTECTED: {
    title: "This content is protected and can't be processed.",
    next: "DRM-protected media is never processed. Try a different source.",
    icon: ShieldAlert,
    tone: "neutral",
  },
  SOURCE_GEO_RESTRICTED: {
    title: "This content isn't available from our server's region.",
    next: "Try a different public source.",
    icon: Globe2,
    tone: "neutral",
  },
  SOURCE_LIVE_STREAM: {
    title: "Live streams can't be processed.",
    next: "Try again once the recording is published.",
    icon: Radio,
    tone: "neutral",
  },
  SOURCE_UNSUPPORTED: {
    title: "We don't support this source yet.",
    next: "Try a direct file link, or upload the file instead.",
    icon: Unlink,
    tone: "neutral",
  },
  FORMAT_UNAVAILABLE: {
    title: "We don't support this format yet.",
    next: "Pick a different option, or try another source.",
    icon: Unlink,
    tone: "neutral",
  },
  FILE_TYPE_UNSUPPORTED: {
    title: "We don't support this file type yet.",
    next: "Check the formats this tool accepts, then try another file.",
    icon: FileWarning,
    tone: "neutral",
  },
  UNSUPPORTED_SCHEME: {
    title: "We can't open this kind of link.",
    next: "Use a regular http or https address.",
    icon: Unlink,
    tone: "neutral",
  },
  INVALID_URL: {
    title: "That doesn't look like a valid link.",
    next: "Check the address and paste it again.",
    icon: Unlink,
    tone: "neutral",
  },
  URL_TOO_LONG: {
    title: "That link is too long.",
    next: "Use a shorter address.",
    icon: Unlink,
    tone: "neutral",
  },
  BLOCKED_TARGET: {
    title: "This address isn't allowed.",
    next: "For safety, private, local and internal network addresses are always blocked.",
    icon: ShieldX,
    tone: "neutral",
  },
  VALIDATION_ERROR: {
    title: "Something's missing.",
    next: "Add a link or a file, then try again.",
    icon: AlertTriangle,
    tone: "warning",
  },
  FILE_TOO_LARGE: {
    title: "This file is too large.",
    next: "Try a smaller file.",
    icon: FileWarning,
    tone: "warning",
  },
  SOURCE_TOO_LARGE: {
    title: "This file is too large.",
    next: "Pick a smaller format or a shorter source.",
    icon: FileWarning,
    tone: "warning",
  },
  SOURCE_NOT_FOUND: {
    title: "We couldn't find that content.",
    next: "It may have been moved or removed. Check the link.",
    icon: SearchX,
    tone: "neutral",
  },
  SOURCE_UNREACHABLE: {
    title: "The source isn't responding right now.",
    next: "This is usually temporary. Try again in a little while.",
    icon: CloudOff,
    tone: "warning",
  },
  SOURCE_FORBIDDEN: {
    title: "The source refused the request.",
    next: "Only content the source shares publicly can be processed.",
    icon: Lock,
    tone: "neutral",
  },
  SOURCE_TIMEOUT: {
    title: "The source took too long to respond.",
    next: "Try again in a moment.",
    icon: Hourglass,
    tone: "warning",
  },
  PROCESSING_TIMEOUT: {
    title: "That took too long to finish.",
    next: "Try a smaller file or a lower quality option.",
    icon: Hourglass,
    tone: "warning",
  },
  QUEUE_FULL: {
    title: "Processing is temporarily unavailable.",
    next: "The service is busy. Try again in a minute.",
    icon: ServerCrash,
    tone: "warning",
  },
  STORAGE_FULL: {
    title: "Processing is temporarily unavailable.",
    next: "The service is short on space. Try again shortly.",
    icon: ServerCrash,
    tone: "warning",
  },
  TOOL_UNAVAILABLE: {
    title: "This tool isn't enabled on this server.",
    next: "Try a related tool instead.",
    icon: ServerCrash,
    tone: "neutral",
  },
  JOB_CANCELLED: {
    title: "Cancelled.",
    next: "Nothing was kept. Start again whenever you like.",
    icon: Ban,
    tone: "neutral",
  },
  CANCELLED: {
    title: "Cancelled.",
    next: "Nothing was kept. Start again whenever you like.",
    icon: Ban,
    tone: "neutral",
  },
  JOB_EXPIRED: {
    title: "This result has expired.",
    next: "Results delete themselves automatically. Run the tool again.",
    icon: Hourglass,
    tone: "neutral",
  },
  EXPIRED: {
    title: "This result has expired.",
    next: "Results delete themselves automatically. Run the tool again.",
    icon: Hourglass,
    tone: "neutral",
  },
  CATALOGUE_FALLBACK: {
    title: "Showing the offline catalogue.",
    next: "Availability is confirmed when you open a tool.",
    icon: CloudOff,
    tone: "warning",
  },
  JOB_NOT_FOUND: {
    title: "We couldn't find that job.",
    next: "It may have expired and been deleted.",
    icon: SearchX,
    tone: "neutral",
  },
};

const FALLBACK: ErrorPresentation = {
  title: "Something went wrong.",
  next: "Please try again.",
  icon: AlertTriangle,
  tone: "danger",
};

export function presentError(error: Pick<ErrorPayload, "code">): ErrorPresentation {
  return BY_CODE[error.code] ?? FALLBACK;
}
