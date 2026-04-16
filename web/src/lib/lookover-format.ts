import type {
  ApiControlResult,
  ApiPreRunScan,
  ApiSpan,
  ApiTraceSummary,
} from "./lookover-api";

export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export function titleCase(value?: string | null) {
  return String(value ?? "")
    .toLowerCase()
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

export function safeText(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => safeText(item)).filter(Boolean).join(", ");
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value && typeof value === "object") {
    return JSON.stringify(value);
  }
  return "";
}

export function formatCompactDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatRelativeTime(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  const deltaSeconds = Math.round((date.getTime() - Date.now()) / 1000);
  const absSeconds = Math.abs(deltaSeconds);
  const formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

  if (absSeconds < 60) {
    return formatter.format(deltaSeconds, "second");
  }
  if (absSeconds < 3600) {
    return formatter.format(Math.round(deltaSeconds / 60), "minute");
  }
  if (absSeconds < 86400) {
    return formatter.format(Math.round(deltaSeconds / 3600), "hour");
  }
  return formatter.format(Math.round(deltaSeconds / 86400), "day");
}

export function formatDuration(start?: string | null, end?: string | null) {
  if (!start) return "—";
  const startDate = new Date(start);
  if (Number.isNaN(startDate.getTime())) return "—";
  if (!end) return "In progress";
  const endDate = new Date(end);
  if (Number.isNaN(endDate.getTime())) return "—";
  const ms = Math.max(0, endDate.getTime() - startDate.getTime());
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3_600_000) return `${(ms / 60_000).toFixed(1)}m`;
  return `${(ms / 3_600_000).toFixed(1)}h`;
}

export function normalizeStatus(value?: string | null) {
  return String(value ?? "").trim().toLowerCase();
}

export function getToneFromStatus(value?: string | null) {
  const normalized = normalizeStatus(value);
  if (
    normalized.includes("violation") ||
    normalized.includes("blocked") ||
    normalized.includes("block") ||
    normalized.includes("error") ||
    normalized.includes("fail")
  ) {
    return "danger";
  }
  if (
    normalized.includes("gap") ||
    normalized.includes("pending") ||
    normalized.includes("partial") ||
    normalized.includes("warn") ||
    normalized.includes("running")
  ) {
    return "warning";
  }
  return "neutral";
}

export function getSeverityTone(value?: string | null) {
  const normalized = normalizeStatus(value);
  if (normalized.includes("critical") || normalized.includes("high")) return "danger";
  if (normalized.includes("medium") || normalized.includes("moderate")) return "warning";
  return "success";
}

export function deriveTraceOutcome(trace: ApiTraceSummary) {
  const metadata = trace.metadata ?? {};
  const explicit = safeText(metadata.outcome || metadata.pipeline_status || metadata.health_status);
  const normalized = normalizeStatus(explicit || trace.status);

  if (normalized.includes("fail") || normalized.includes("error") || normalized.includes("blocked")) {
    return "Failure";
  }
  if (normalized.includes("running") || normalized.includes("pending")) {
    return "In Progress";
  }
  return "Success";
}

export function deriveRootIntent(trace: ApiTraceSummary, spans?: ApiSpan[]) {
  const metadata = trace.metadata ?? {};
  const fromMetadata =
    safeText(metadata.root_intent) ||
    safeText(metadata.intent) ||
    safeText(metadata.summary) ||
    safeText(metadata.purpose);

  if (fromMetadata) return fromMetadata;

  const rootSpan = spans?.find((span) => !span.parent_span_id);
  if (rootSpan?.name) return rootSpan.name;

  if (trace.use_case_category) {
    return titleCase(trace.use_case_category);
  }

  return "Review agent trace";
}

export function getRiskLabel(score?: number | null) {
  const numeric = typeof score === "number" ? score : 0;
  if (numeric >= 80) return "High";
  if (numeric >= 50) return "Moderate";
  if (numeric > 0) return "Low";
  return "None";
}

export function countSpansForTrace(spans: ApiSpan[]) {
  return spans.length;
}

export function countFindingsByCategory(findings: ApiControlResult[]) {
  return findings.reduce(
    (accumulator, finding) => {
      const normalized = normalizeStatus(finding.status);
      if (normalized.includes("cover")) accumulator.covered += 1;
      else if (normalized.includes("gap") || normalized.includes("partial")) accumulator.gaps += 1;
      else accumulator.violations += 1;
      return accumulator;
    },
    { violations: 0, gaps: 0, covered: 0 },
  );
}

export function extractSummaryMetric(scan: ApiPreRunScan, key: string) {
  const value = scan.summary?.[key];
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? 0 : parsed;
  }
  return 0;
}
