import "server-only";

import { cookies } from "next/headers";
import { getConfiguredApiBaseUrl } from "./lookover-config";

export type ShareMode = "audit_log_only" | "audit_log_plus_evaluation";

export type ApiTraceSummary = {
  trace_id: string;
  session_id: string;
  agent_id: string;
  agent_version: string;
  framework: string;
  model_id: string;
  model_provider: string;
  model_version: string;
  ai_act_risk_tier: string;
  use_case_category: string;
  environment: string;
  overall_risk_score: number;
  status: string;
  created_at: string;
  updated_at: string;
  metadata: Record<string, unknown>;
  span_count: number;
};

export type ApiSpan = {
  span_id: string;
  trace_id: string;
  parent_span_id: string;
  name: string;
  event_type: string;
  status: string;
  start_time: string;
  end_time: string;
  payload: Record<string, unknown>;
};

export type ApiEvidence = {
  id: string;
  trace_id: string;
  span_id: string;
  source: string;
  field_name: string;
  value: Record<string, unknown>;
  previous_hash: string;
  payload_hash: string;
  chain_hash: string;
  signed_chain_hash: string;
  created_at: string;
};

export type ApiControlResult = {
  id: string;
  trace_id: string;
  span_id?: string;
  framework: string;
  control_id: string;
  title: string;
  citation: string;
  status: string;
  severity: string;
  priority: string;
  reasoning: string;
  residual_risk: string;
  remediation: string;
  observed_evidence: Record<string, unknown>;
  created_at: string;
};

export type ApiTraceDetail = {
  trace: ApiTraceSummary;
  spans: ApiSpan[];
  evidence: ApiEvidence[];
  findings: ApiControlResult[];
  control_summary: Record<string, number>;
};

export type ApiPreRunFinding = {
  id: string;
  rule_id: string;
  title: string;
  severity: string;
  status: string;
  control_refs: string[];
  evidence: Record<string, unknown>;
  remediation: string;
};

export type ApiPreRunScan = {
  scan_id: string;
  project_path: string;
  strict_mode: boolean;
  readiness_score: number;
  strict_result: string;
  frameworks: string[];
  summary: Record<string, unknown>;
  findings: ApiPreRunFinding[];
  created_at: string;
};

export type ApiShareDetail = {
  share_id: string;
  mode: ShareMode;
  trace: ApiTraceDetail;
  read_only: boolean;
};

type ApiFetchResult<T> = {
  data: T | null;
  status: number | null;
};

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map((item) => String(item));
}

function asNumber(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function normalizeTraceSummary(trace: Partial<ApiTraceSummary> | null | undefined): ApiTraceSummary {
  return {
    trace_id: String(trace?.trace_id ?? ""),
    session_id: String(trace?.session_id ?? ""),
    agent_id: String(trace?.agent_id ?? ""),
    agent_version: String(trace?.agent_version ?? ""),
    framework: String(trace?.framework ?? ""),
    model_id: String(trace?.model_id ?? ""),
    model_provider: String(trace?.model_provider ?? ""),
    model_version: String(trace?.model_version ?? ""),
    ai_act_risk_tier: String(trace?.ai_act_risk_tier ?? ""),
    use_case_category: String(trace?.use_case_category ?? ""),
    environment: String(trace?.environment ?? ""),
    overall_risk_score: asNumber(trace?.overall_risk_score),
    status: String(trace?.status ?? ""),
    created_at: String(trace?.created_at ?? ""),
    updated_at: String(trace?.updated_at ?? ""),
    metadata: asRecord(trace?.metadata),
    span_count: asNumber(trace?.span_count),
  };
}

function normalizeSpan(span: Partial<ApiSpan> | null | undefined): ApiSpan {
  return {
    span_id: String(span?.span_id ?? ""),
    trace_id: String(span?.trace_id ?? ""),
    parent_span_id: String(span?.parent_span_id ?? ""),
    name: String(span?.name ?? ""),
    event_type: String(span?.event_type ?? ""),
    status: String(span?.status ?? ""),
    start_time: String(span?.start_time ?? ""),
    end_time: String(span?.end_time ?? ""),
    payload: asRecord(span?.payload),
  };
}

function normalizeEvidence(evidence: Partial<ApiEvidence> | null | undefined): ApiEvidence {
  return {
    id: String(evidence?.id ?? ""),
    trace_id: String(evidence?.trace_id ?? ""),
    span_id: String(evidence?.span_id ?? ""),
    source: String(evidence?.source ?? ""),
    field_name: String(evidence?.field_name ?? ""),
    value: asRecord(evidence?.value),
    previous_hash: String(evidence?.previous_hash ?? ""),
    payload_hash: String(evidence?.payload_hash ?? ""),
    chain_hash: String(evidence?.chain_hash ?? ""),
    signed_chain_hash: String(evidence?.signed_chain_hash ?? ""),
    created_at: String(evidence?.created_at ?? ""),
  };
}

function normalizeControlResult(result: Partial<ApiControlResult> | null | undefined): ApiControlResult {
  return {
    id: String(result?.id ?? ""),
    trace_id: String(result?.trace_id ?? ""),
    span_id: result?.span_id ? String(result.span_id) : undefined,
    framework: String(result?.framework ?? ""),
    control_id: String(result?.control_id ?? ""),
    title: String(result?.title ?? ""),
    citation: String(result?.citation ?? ""),
    status: String(result?.status ?? ""),
    severity: String(result?.severity ?? ""),
    priority: String(result?.priority ?? ""),
    reasoning: String(result?.reasoning ?? ""),
    residual_risk: String(result?.residual_risk ?? ""),
    remediation: String(result?.remediation ?? ""),
    observed_evidence: asRecord(result?.observed_evidence),
    created_at: String(result?.created_at ?? ""),
  };
}

function normalizeTraceDetail(detail: Partial<ApiTraceDetail> | null | undefined): ApiTraceDetail | null {
  if (!detail?.trace) {
    return null;
  }

  return {
    trace: normalizeTraceSummary(detail.trace),
    spans: Array.isArray(detail.spans) ? detail.spans.map(normalizeSpan) : [],
    evidence: Array.isArray(detail.evidence) ? detail.evidence.map(normalizeEvidence) : [],
    findings: Array.isArray(detail.findings) ? detail.findings.map(normalizeControlResult) : [],
    control_summary: asRecord(detail.control_summary) as Record<string, number>,
  };
}

function normalizePreRunFinding(finding: Partial<ApiPreRunFinding> | null | undefined): ApiPreRunFinding {
  return {
    id: String(finding?.id ?? ""),
    rule_id: String(finding?.rule_id ?? ""),
    title: String(finding?.title ?? ""),
    severity: String(finding?.severity ?? ""),
    status: String(finding?.status ?? ""),
    control_refs: asStringArray(finding?.control_refs),
    evidence: asRecord(finding?.evidence),
    remediation: String(finding?.remediation ?? ""),
  };
}

function normalizePreRunScan(scan: Partial<ApiPreRunScan> | null | undefined): ApiPreRunScan {
  return {
    scan_id: String(scan?.scan_id ?? ""),
    project_path: String(scan?.project_path ?? ""),
    strict_mode: Boolean(scan?.strict_mode),
    readiness_score: asNumber(scan?.readiness_score),
    strict_result: String(scan?.strict_result ?? ""),
    frameworks: asStringArray(scan?.frameworks),
    summary: asRecord(scan?.summary),
    findings: Array.isArray(scan?.findings) ? scan.findings.map(normalizePreRunFinding) : [],
    created_at: String(scan?.created_at ?? ""),
  };
}

function normalizeShareDetail(share: Partial<ApiShareDetail> | null | undefined): ApiShareDetail | null {
  const trace = normalizeTraceDetail(share?.trace);
  if (!share?.share_id || !trace) {
    return null;
  }

  return {
    share_id: String(share.share_id),
    mode: share.mode === "audit_log_only" ? "audit_log_only" : "audit_log_plus_evaluation",
    trace,
    read_only: Boolean(share.read_only),
  };
}

async function fetchJsonDetailed<T>(
  path: string,
  init: RequestInit = {},
  origin?: string,
): Promise<ApiFetchResult<T>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2500);

  try {
    const requestOrigin = origin ?? getConfiguredApiBaseUrl();
    const response = await fetch(new URL(path, requestOrigin).toString(), {
      cache: "no-store",
      ...init,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(init.headers ?? {}),
      },
    });

    if (!response.ok) {
      return { data: null, status: response.status };
    }

    return { data: (await response.json()) as T, status: response.status };
  } catch {
    return { data: null, status: null };
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchJson<T>(path: string, init: RequestInit = {}, origin?: string) {
  const result = await fetchJsonDetailed<T>(path, init, origin);
  return result.data;
}

export async function listTraces(origin?: string) {
  const payload = await fetchJson<{ items: ApiTraceSummary[] }>("/v1/traces", {}, origin);
  return Array.isArray(payload?.items) ? payload.items.map(normalizeTraceSummary) : [];
}

export async function getTraceDetail(traceId: string, origin?: string) {
  return normalizeTraceDetail(await fetchJson<ApiTraceDetail>(`/v1/traces/${traceId}`, {}, origin));
}

export async function listPreRunScans(origin?: string) {
  const payload = await fetchJson<{ items: ApiPreRunScan[] }>("/v1/prerun/scans", {}, origin);
  return Array.isArray(payload?.items) ? payload.items.map(normalizePreRunScan) : [];
}

export async function getPreRunScan(scanId: string, origin?: string) {
  const scan = await fetchJson<ApiPreRunScan>(`/v1/prerun/scans/${scanId}`, {}, origin);
  return scan ? normalizePreRunScan(scan) : null;
}

export async function getLatestTraceId() {
  const traces = await listTraces();
  return traces[0]?.trace_id ?? null;
}

export async function getLatestPreRunScanId() {
  const scans = await listPreRunScans();
  return scans[0]?.scan_id ?? null;
}

export async function getSharedTrace(shareId: string, origin?: string) {
  const cookieStore = await cookies();
  const token = cookieStore.get("lookover_session_token")?.value?.trim();
  const headersInit: Record<string, string> = {};

  if (token) {
    headersInit.Authorization = `Bearer ${token}`;
  }

  return normalizeShareDetail(
    await fetchJson<ApiShareDetail>(
      `/v1/shared/${shareId}`,
      {
        headers: headersInit,
      },
      origin,
    ),
  );
}

export function getReviewerFromCookie(rawValue?: string | null) {
  if (!rawValue) {
    return null;
  }

  try {
    const parsed = JSON.parse(rawValue) as { email?: string; role?: string };
    return {
      email: String(parsed.email ?? "reviewer@lookover.local"),
      role: String(parsed.role ?? "reviewer"),
    };
  } catch {
    return {
      email: "reviewer@lookover.local",
      role: "reviewer",
    };
  }
}
