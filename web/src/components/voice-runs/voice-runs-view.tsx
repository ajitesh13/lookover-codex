"use client";

import { useMemo, useState } from "react";
import { AlertCircle, Mic, ShieldCheck, Waves } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ApiVoiceRunFilters, ApiVoiceRunRecord, ApiVoiceRunsListResponse } from "@/lib/lookover-api";
import { formatCompactDate, formatRelativeTime } from "@/lib/lookover-format";

const initialDraftFilters: ApiVoiceRunFilters = {
  query: "",
  disposition: "",
  status: "",
  tenant: "",
  deployer: "",
  applicability: "",
  ai_disclosure_status: "",
  article: "",
  severity: "",
  from: "",
  to: "",
  high_risk_flag: "",
  emotion_or_biometric_features: "",
  human_handoff: "",
  page: 1,
  page_size: 25,
};

const badgeTone: Record<string, "neutral" | "success" | "warning" | "danger"> = {
  completed: "success",
  failed: "danger",
  pending: "warning",
  pass: "success",
  fail: "danger",
  needs_review: "warning",
  hard_fail: "danger",
  soft_fail: "danger",
  not_applicable: "neutral",
  not_evaluable_from_logs: "neutral",
};

function toneFor(value: string) {
  return badgeTone[value] ?? "neutral";
}

function findingsSummary(record: ApiVoiceRunRecord) {
  if (record.failing_finding_count > 0) {
    return `${record.failing_finding_count} failing article checks`;
  }
  if (record.needs_review_finding_count > 0) {
    return `${record.needs_review_finding_count} articles need review`;
  }
  return `${record.finding_count} article checks passed or were not applicable`;
}

function topArticleCounts(records: ApiVoiceRunRecord[]) {
  const counts = new Map<string, number>();
  for (const record of records) {
    for (const finding of record.findings) {
      const key = `${finding.article}:${finding.status}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
}

function VoiceRunResult({ record }: { record: ApiVoiceRunRecord }) {
  return (
    <section className="lookover-card overflow-hidden">
      <div className="border-b border-lookover-border px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="lookover-label">Stored audit</div>
            <h2 className="mt-2 text-[20px] font-semibold tracking-[-0.03em] text-slate-900">{record.call_id}</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={toneFor(record.status)}>{record.status.replaceAll("_", " ")}</Badge>
            <Badge tone={toneFor(record.disposition)}>{record.disposition.replaceAll("_", " ")}</Badge>
            <Badge tone="neutral">{record.applicability.replaceAll("_", " ")}</Badge>
          </div>
        </div>
      </div>
      <div className="grid gap-5 px-6 py-6 xl:grid-cols-[0.95fr,1.05fr]">
        <div className="space-y-4">
          <div>
            <div className="lookover-label">Parsed transcript</div>
            <div className="mt-3 space-y-3">
              {record.transcript_turns.map((turn, index) => (
                <div key={`${turn.timestamp_seconds}-${index}`} className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500">{turn.speaker}</span>
                    <span className="text-[12px] text-lookover-text-muted">{turn.timestamp_seconds.toFixed(1)}s</span>
                  </div>
                  <p className="mt-2 text-[14px] leading-6 text-slate-900">{turn.text}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="space-y-4">
          <div>
            <div className="lookover-label">Findings</div>
            <div className="mt-3 space-y-3">
              {record.findings.map((finding, index) => (
                <div key={`${finding.article}-${index}`} className="rounded-2xl border border-lookover-border bg-white px-4 py-4 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={toneFor(finding.status)}>{finding.status.replaceAll("_", " ")}</Badge>
                    <span className="text-[13px] font-semibold text-slate-900">Article {finding.article}</span>
                    <span className="text-[12px] uppercase tracking-[0.12em] text-lookover-text-muted">{finding.severity}</span>
                  </div>
                  <p className="mt-3 text-[14px] leading-6 text-slate-700">{finding.reason}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export function VoiceRunsView({ initialResponse }: { initialResponse: ApiVoiceRunsListResponse | null }) {
  const [response, setResponse] = useState<ApiVoiceRunsListResponse | null>(initialResponse);
  const [draftFilters, setDraftFilters] = useState<ApiVoiceRunFilters>(initialDraftFilters);
  const [appliedFilters, setAppliedFilters] = useState<ApiVoiceRunFilters>(initialDraftFilters);
  const [loading, setLoading] = useState(false);
  const [transcript, setTranscript] = useState(
    "Agent: Hello, I am an AI assistant calling on behalf of the service team.\nCustomer: Are you a real person?\nAgent: I can transfer you to a human colleague if you prefer.",
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestRecord, setLatestRecord] = useState<ApiVoiceRunRecord | null>(null);

  const articleCounts = useMemo(() => topArticleCounts(response?.items ?? []), [response]);

  async function loadVoiceRuns(filters: ApiVoiceRunFilters) {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      for (const [key, value] of Object.entries(filters)) {
        if (value === undefined || value === null || value === "") continue;
        params.set(key, String(value));
      }

      const target = params.size > 0 ? `/api/voice-runs?${params.toString()}` : "/api/voice-runs";
      const fetchResponse = await fetch(target, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      });
      const payload = (await fetchResponse.json()) as ApiVoiceRunsListResponse & { error?: string };
      if (!fetchResponse.ok) {
        throw new Error(payload.error || "Voice runs could not be loaded.");
      }
      setResponse(payload);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Voice runs could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  async function applyFilters() {
    const nextFilters = { ...draftFilters, page: 1 };
    setAppliedFilters(nextFilters);
    await loadVoiceRuns(nextFilters);
  }

  async function goToPage(page: number) {
    const nextFilters = { ...appliedFilters, page };
    setAppliedFilters(nextFilters);
    await loadVoiceRuns(nextFilters);
  }

  async function runTranscriptAudit() {
    setSubmitting(true);
    setError(null);
    try {
      const fetchResponse = await fetch("/api/voice-runs", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ transcript }),
      });

      const payload = (await fetchResponse.json()) as ApiVoiceRunRecord & { error?: string };
      if (!fetchResponse.ok) {
        throw new Error(payload.error || "Transcript audit failed.");
      }

      setLatestRecord(payload);
      await loadVoiceRuns(appliedFilters);
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : "Transcript audit failed.";
      await loadVoiceRuns(appliedFilters);
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const pageSize = appliedFilters.page_size ?? 25;
  const currentPage = appliedFilters.page ?? 1;
  const totalPages = Math.max(1, Math.ceil((response?.total ?? 0) / pageSize));

  return (
    <div className="space-y-6">
      <div className="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <div className="lookover-label">Voice auditor</div>
                <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.04em] text-slate-900">Voice Runs</h1>
                <p className="mt-2 max-w-[56ch] text-[14px] leading-6 text-lookover-text-muted">
                  Backend-owned voice audits with stored reports, operational filters, and transcript-driven submission through the main post-run API.
                </p>
              </div>
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-3 text-right">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">Latest sync</div>
                <div className="mt-2 text-[14px] font-medium text-slate-900">
                  {response?.items[0]?.updated_at ? formatCompactDate(response.items[0].updated_at) : "Unavailable"}
                </div>
                <div className="mt-1 text-[12px] text-lookover-text-muted">
                  {response?.items[0]?.updated_at ? formatRelativeTime(response.items[0].updated_at) : "No stored voice runs yet."}
                </div>
              </div>
            </div>
          </div>
          <div className="grid gap-4 px-6 py-6 md:grid-cols-4">
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Audited</span>
                <Mic className="h-4 w-4 text-slate-400" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {response?.summary.total ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Hard fail</span>
                <AlertCircle className="h-4 w-4 text-rose-400" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {response?.summary.hard_fail ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Needs review</span>
                <Waves className="h-4 w-4 text-amber-500" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {response?.summary.needs_review ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Passing</span>
                <ShieldCheck className="h-4 w-4 text-emerald-500" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {response?.summary.pass ?? 0}
              </div>
            </div>
          </div>
        </section>

        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Run Transcript Through Backend</h2>
            <p className="mt-2 text-[14px] leading-6 text-lookover-text-muted">
              Submit a transcript to the backend post-run API. The backend stores the record, calls `voice-auditor`, and persists the returned audit report.
            </p>
          </div>
          <div className="px-6 py-6">
            <textarea
              className="min-h-[220px] w-full rounded-2xl border border-lookover-border bg-white px-4 py-4 text-[14px] leading-6 text-slate-900 outline-none transition focus:border-slate-300 focus:ring-2 focus:ring-slate-200"
              value={transcript}
              onChange={(event) => setTranscript(event.target.value)}
              placeholder="Agent: Hello, I am an AI assistant..."
            />
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <div className="text-[13px] text-lookover-text-muted">A stored backend record is created for each submission, even when the downstream voice audit fails.</div>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center rounded-xl bg-[#111113] px-5 text-[13px] font-semibold text-white transition hover:bg-[#1b1b20] disabled:cursor-not-allowed disabled:opacity-60"
                onClick={runTranscriptAudit}
                disabled={submitting}
              >
                {submitting ? "Running audit..." : "Create voice run"}
              </button>
            </div>
          </div>
        </section>
      </div>

      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-600">{error}</div>
      ) : null}

      {latestRecord ? <VoiceRunResult record={latestRecord} /> : null}

      <section className="lookover-card px-5 py-5">
        <div className="grid gap-4 xl:grid-cols-[1.2fr,0.9fr,0.9fr,0.9fr,0.9fr,0.9fr]">
          <input
            className="lookover-input"
            value={draftFilters.query}
            onChange={(event) => setDraftFilters((value) => ({ ...value, query: event.target.value }))}
            placeholder="Search call ID or transcript"
          />
          <select
            className="lookover-input"
            value={draftFilters.disposition}
            onChange={(event) => setDraftFilters((value) => ({ ...value, disposition: event.target.value }))}
          >
            <option value="">All dispositions</option>
            <option value="pass">Pass</option>
            <option value="needs_review">Needs review</option>
            <option value="hard_fail">Hard fail</option>
          </select>
          <select
            className="lookover-input"
            value={draftFilters.status}
            onChange={(event) => setDraftFilters((value) => ({ ...value, status: event.target.value }))}
          >
            <option value="">All statuses</option>
            <option value="completed">Completed</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
          <input
            className="lookover-input"
            value={draftFilters.tenant}
            onChange={(event) => setDraftFilters((value) => ({ ...value, tenant: event.target.value }))}
            placeholder="Tenant"
          />
          <input
            className="lookover-input"
            value={draftFilters.deployer}
            onChange={(event) => setDraftFilters((value) => ({ ...value, deployer: event.target.value }))}
            placeholder="Deployer"
          />
          <button
            type="button"
            className="inline-flex h-10 items-center justify-center rounded-xl bg-[#111113] px-5 text-[13px] font-semibold text-white transition hover:bg-[#1b1b20] disabled:opacity-60"
            onClick={applyFilters}
            disabled={loading}
          >
            {loading ? "Loading..." : "Apply filters"}
          </button>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-6">
          <select
            className="lookover-input"
            value={draftFilters.applicability}
            onChange={(event) => setDraftFilters((value) => ({ ...value, applicability: event.target.value }))}
          >
            <option value="">All applicability</option>
            <option value="transparency_only">Transparency only</option>
            <option value="transparency_plus_biometrics">Transparency + biometrics</option>
            <option value="potential_high_risk">Potential high risk</option>
            <option value="high_risk_confirmed">High risk confirmed</option>
          </select>
          <select
            className="lookover-input"
            value={draftFilters.ai_disclosure_status}
            onChange={(event) => setDraftFilters((value) => ({ ...value, ai_disclosure_status: event.target.value }))}
          >
            <option value="">All disclosure states</option>
            <option value="present">Present</option>
            <option value="missing">Missing</option>
            <option value="unknown">Unknown</option>
          </select>
          <input
            className="lookover-input"
            value={draftFilters.article}
            onChange={(event) => setDraftFilters((value) => ({ ...value, article: event.target.value }))}
            placeholder="Article"
          />
          <input
            className="lookover-input"
            value={draftFilters.severity}
            onChange={(event) => setDraftFilters((value) => ({ ...value, severity: event.target.value }))}
            placeholder="Severity"
          />
          <input
            className="lookover-input"
            type="date"
            value={draftFilters.from}
            onChange={(event) => setDraftFilters((value) => ({ ...value, from: event.target.value }))}
          />
          <input
            className="lookover-input"
            type="date"
            value={draftFilters.to}
            onChange={(event) => setDraftFilters((value) => ({ ...value, to: event.target.value }))}
          />
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          <select
            className="lookover-input"
            value={draftFilters.high_risk_flag}
            onChange={(event) => setDraftFilters((value) => ({ ...value, high_risk_flag: event.target.value }))}
          >
            <option value="">All high-risk states</option>
            <option value="true">High risk</option>
            <option value="false">Not high risk</option>
          </select>
          <select
            className="lookover-input"
            value={draftFilters.emotion_or_biometric_features}
            onChange={(event) =>
              setDraftFilters((value) => ({ ...value, emotion_or_biometric_features: event.target.value }))
            }
          >
            <option value="">All biometric states</option>
            <option value="true">Emotion or biometric used</option>
            <option value="false">No emotion or biometric use</option>
          </select>
          <select
            className="lookover-input"
            value={draftFilters.human_handoff}
            onChange={(event) => setDraftFilters((value) => ({ ...value, human_handoff: event.target.value }))}
          >
            <option value="">All handoff states</option>
            <option value="true">Human handoff path present</option>
            <option value="false">No human handoff path</option>
          </select>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Article Status Hotspots</h2>
          </div>
          <div className="space-y-3 px-6 py-6">
            {articleCounts.map(([key, count]) => {
              const [article, status] = key.split(":");
              return (
                <div key={key} className="flex items-center justify-between rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-3">
                  <div>
                    <div className="text-[14px] font-medium text-slate-900">Article {article}</div>
                    <div className="mt-1 text-[12px] uppercase tracking-[0.12em] text-lookover-text-muted">{status}</div>
                  </div>
                  <div className="text-[22px] font-semibold tracking-[-0.04em] text-slate-900">{count}</div>
                </div>
              );
            })}
            {articleCounts.length === 0 ? (
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-8 text-center text-[14px] text-lookover-text-muted">
                No article count data is available for the current filter set.
              </div>
            ) : null}
          </div>
        </section>

        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Stored Voice Runs</h2>
              <div className="text-[13px] text-lookover-text-muted">{response?.total ?? 0} matching backend records</div>
            </div>
          </div>
          <div className="space-y-4 px-6 py-6">
            {(response?.items ?? []).map((record) => (
              <details key={record.voice_run_id} className="rounded-[20px] border border-lookover-border bg-white">
                <summary className="cursor-pointer list-none px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="lookover-label">Voice run</div>
                      <h3 className="mt-2 text-[18px] font-semibold tracking-[-0.03em] text-slate-900">{record.call_id}</h3>
                      <p className="mt-2 max-w-[64ch] text-[14px] leading-6 text-lookover-text-muted">
                        {record.transcript_text || "Stored voice-run transcript"}
                      </p>
                      <div className="mt-3 text-[13px] text-lookover-text-muted">{findingsSummary(record)}</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={toneFor(record.status)}>{record.status.replaceAll("_", " ")}</Badge>
                      <Badge tone={toneFor(record.disposition)}>{record.disposition.replaceAll("_", " ")}</Badge>
                    </div>
                  </div>
                </summary>
                <div className="border-t border-lookover-border px-5 py-5">
                  <div className="grid gap-5 xl:grid-cols-[0.92fr,1.08fr]">
                    <div className="space-y-4">
                      <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-4">
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <div className="lookover-label">Created</div>
                            <div className="mt-2 text-[14px] text-slate-900">{formatCompactDate(record.created_at)}</div>
                          </div>
                          <div>
                            <div className="lookover-label">Applicability</div>
                            <div className="mt-2 text-[14px] text-slate-900">{record.applicability.replaceAll("_", " ")}</div>
                          </div>
                          <div>
                            <div className="lookover-label">Tenant / Deployer</div>
                            <div className="mt-2 text-[14px] text-slate-900">{record.tenant} / {record.deployer}</div>
                          </div>
                          <div>
                            <div className="lookover-label">Disclosure</div>
                            <div className="mt-2 text-[14px] text-slate-900">{record.ai_disclosure_status.replaceAll("_", " ")}</div>
                          </div>
                        </div>
                      </div>
                      <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-4">
                        <div className="lookover-label">Transcript Preview</div>
                        <div className="mt-3 space-y-3">
                          {record.transcript_preview.map((turn, index) => (
                            <div key={`${record.voice_run_id}-${index}`} className="rounded-xl border border-white/70 bg-white px-3 py-3">
                              <div className="flex items-center justify-between gap-3">
                                <span className="text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500">{turn.speaker}</span>
                                <span className="text-[12px] text-lookover-text-muted">{turn.timestamp_seconds.toFixed(1)}s</span>
                              </div>
                              <p className="mt-2 text-[14px] leading-6 text-slate-900">{turn.text}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-4">
                        <div className="lookover-label">Event Timeline</div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          {record.timeline.map((item, index) => (
                            <div key={`${record.voice_run_id}-timeline-${index}`} className="rounded-full border border-lookover-border bg-white px-3 py-2 text-[13px] text-slate-700">
                              <span className="font-medium">{item.event}</span> at {item.timestamp_seconds.toFixed(1)}s
                            </div>
                          ))}
                          {record.timeline.length === 0 ? (
                            <div className="text-[13px] text-lookover-text-muted">No timeline events were returned for this run.</div>
                          ) : null}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-lookover-border bg-white">
                        <table className="min-w-full">
                          <thead className="border-b border-lookover-border bg-slate-50/70">
                            <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
                              <th className="px-4 py-3.5">Article</th>
                              <th className="px-4 py-3.5">Status</th>
                              <th className="px-4 py-3.5">Severity</th>
                              <th className="px-4 py-3.5">Reason</th>
                            </tr>
                          </thead>
                          <tbody>
                            {record.findings.map((finding, index) => (
                              <tr key={`${record.voice_run_id}-finding-${index}`} className="border-b border-lookover-border/70 align-top last:border-b-0">
                                <td className="lookover-table-cell font-medium">Article {finding.article}</td>
                                <td className="lookover-table-cell">
                                  <Badge tone={toneFor(finding.status)}>{finding.status.replaceAll("_", " ")}</Badge>
                                </td>
                                <td className="lookover-table-cell text-lookover-text-muted">{finding.severity}</td>
                                <td className="lookover-table-cell text-lookover-text-muted">{finding.reason}</td>
                              </tr>
                            ))}
                            {record.findings.length === 0 ? (
                              <tr>
                                <td colSpan={4} className="px-5 py-8 text-center text-[14px] text-lookover-text-muted">
                                  No findings are stored for this run.
                                </td>
                              </tr>
                            ) : null}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>
              </details>
            ))}
            {(response?.items.length ?? 0) === 0 ? (
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-12 text-center text-[15px] text-lookover-text-muted">
                No voice runs match the current filters.
              </div>
            ) : null}
          </div>
          <div className="flex items-center justify-between px-5 py-4 text-[13px] text-lookover-text-muted">
            <span>{response?.total ?? 0} total voice runs</span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                className="rounded-lg border border-lookover-border px-3 py-2 transition hover:bg-slate-50 disabled:opacity-50"
                onClick={() => goToPage(Math.max(1, currentPage - 1))}
                disabled={currentPage <= 1 || loading}
              >
                Previous
              </button>
              <span>
                {currentPage} / {totalPages}
              </span>
              <button
                type="button"
                className="rounded-lg border border-lookover-border px-3 py-2 transition hover:bg-slate-50 disabled:opacity-50"
                onClick={() => goToPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage >= totalPages || loading}
              >
                Next
              </button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
