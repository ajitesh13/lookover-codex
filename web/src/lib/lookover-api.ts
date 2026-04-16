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
  return payload?.items ?? [];
}

export async function getTraceDetail(traceId: string, origin?: string) {
  return await fetchJson<ApiTraceDetail>(`/v1/traces/${traceId}`, {}, origin);
}

export async function listPreRunScans(origin?: string) {
  const payload = await fetchJson<{ items: ApiPreRunScan[] }>("/v1/prerun/scans", {}, origin);
  return payload?.items ?? [];
}

export async function getPreRunScan(scanId: string, origin?: string) {
  return await fetchJson<ApiPreRunScan>(`/v1/prerun/scans/${scanId}`, {}, origin);
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

  return await fetchJson<ApiShareDetail>(
    `/v1/shared/${shareId}`,
    {
      headers: headersInit,
    },
    origin,
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
