"use client";

import { useMemo, useState } from "react";
import { AlertCircle, Mic, Waves, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ApiVoiceFinding, ApiVoiceRunsReport, ApiVoiceRunRecord } from "@/lib/lookover-api";
import { formatCompactDate, formatRelativeTime } from "@/lib/lookover-format";

type TranscriptAuditResponse = {
  record: {
    call_id: string;
    disposition: string;
    applicability: string;
    findings: ApiVoiceFinding[];
    event_timeline: Array<{ event: string; timestamp_seconds: number }>;
    transcript_turns: Array<{ speaker: string; text: string; timestamp_seconds: number }>;
  };
  transcript_turns: Array<{ speaker: string; text: string; timestamp_seconds: number }>;
};

const dispositionTone: Record<string, "neutral" | "success" | "warning" | "danger"> = {
  fail: "danger",
  pass: "success",
  needs_review: "warning",
  not_applicable: "neutral",
  not_evaluable_from_logs: "neutral",
  soft_fail: "danger",
  hard_fail: "danger",
};

function getDispositionTone(value: string) {
  return dispositionTone[value] ?? "neutral";
}

function summarizeArticles(counts: Record<string, number>) {
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
}

function findingsSummary(record: ApiVoiceRunRecord) {
  const failing = record.findings.filter((item) => item.status === "fail").length;
  const review = record.findings.filter((item) => item.status === "needs_review").length;
  if (failing > 0) return `${failing} failing article checks`;
  if (review > 0) return `${review} articles need review`;
  return `${record.findings.length} article checks passed or not applicable`;
}

function TranscriptResult({ result }: { result: TranscriptAuditResponse }) {
  return (
    <section className="lookover-card overflow-hidden">
      <div className="border-b border-lookover-border px-6 py-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="lookover-label">Ad hoc audit</div>
            <h2 className="mt-2 text-[20px] font-semibold tracking-[-0.03em] text-slate-900">{result.record.call_id}</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={getDispositionTone(result.record.disposition)}>{result.record.disposition.replaceAll("_", " ")}</Badge>
            <Badge tone="neutral">{result.record.applicability.replaceAll("_", " ")}</Badge>
          </div>
        </div>
      </div>
      <div className="grid gap-5 px-6 py-6 xl:grid-cols-[0.95fr,1.05fr]">
        <div className="space-y-4">
          <div>
            <div className="lookover-label">Parsed transcript</div>
            <div className="mt-3 space-y-3">
              {result.transcript_turns.map((turn, index) => (
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
              {result.record.findings.map((finding, index) => (
                <div key={`${finding.article}-${index}`} className="rounded-2xl border border-lookover-border bg-white px-4 py-4 shadow-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={getDispositionTone(finding.status)}>{finding.status.replaceAll("_", " ")}</Badge>
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

export function VoiceRunsView({ report }: { report: ApiVoiceRunsReport | null }) {
  const [transcript, setTranscript] = useState(
    "Agent: Hello, I am an AI assistant calling on behalf of the service team.\nCustomer: Are you a real person?\nAgent: I can transfer you to a human colleague if you prefer.",
  );
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<TranscriptAuditResponse | null>(null);

  const topArticleCounts = useMemo(() => summarizeArticles(report?.article_status_counts ?? {}), [report]);
  const featuredRecords = report?.records.slice(0, 12) ?? [];

  async function runTranscriptAudit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const response = await fetch("/api/voice-runs/audit", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ transcript }),
      });

      const payload = (await response.json()) as TranscriptAuditResponse & { error?: string };
      if (!response.ok) {
        throw new Error(payload.error || "Transcript audit failed.");
      }

      setResult(payload);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Transcript audit failed.");
    } finally {
      setSubmitting(false);
    }
  }

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
                  Detailed call-center audit runs from the isolated Voice Logs Auditor, including report-level counts and per-run article findings.
                </p>
              </div>
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-3 text-right">
                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">Latest report</div>
                <div className="mt-2 text-[14px] font-medium text-slate-900">
                  {report?.generated_at ? formatCompactDate(report.generated_at) : "Unavailable"}
                </div>
                <div className="mt-1 text-[12px] text-lookover-text-muted">
                  {report?.generated_at ? formatRelativeTime(report.generated_at) : "Voice auditor is not serving report data."}
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
                {report?.audited_records ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Hard fail</span>
                <AlertCircle className="h-4 w-4 text-rose-400" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {report?.disposition_counts.hard_fail ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Needs review</span>
                <Waves className="h-4 w-4 text-amber-500" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {report?.disposition_counts.needs_review ?? 0}
              </div>
            </div>
            <div className="rounded-2xl border border-lookover-border bg-white px-4 py-4">
              <div className="flex items-center justify-between">
                <span className="lookover-label">Passing</span>
                <ShieldCheck className="h-4 w-4 text-emerald-500" />
              </div>
              <div className="mt-4 text-[34px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
                {report?.disposition_counts.pass ?? 0}
              </div>
            </div>
          </div>
        </section>

        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Run Transcript Through Auditor</h2>
            <p className="mt-2 text-[14px] leading-6 text-lookover-text-muted">
              Paste a transcript using either freeform text or speaker-prefixed lines like <code>Agent:</code> and <code>Customer:</code>.
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
              <div className="text-[13px] text-lookover-text-muted">This creates an isolated voice-audit record and returns the compliance findings immediately.</div>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-center rounded-xl bg-[#111113] px-5 text-[13px] font-semibold text-white transition hover:bg-[#1b1b20] disabled:cursor-not-allowed disabled:opacity-60"
                onClick={runTranscriptAudit}
                disabled={submitting}
              >
                {submitting ? "Running audit..." : "Run voice audit"}
              </button>
            </div>
            {submitError ? (
              <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] text-rose-600">{submitError}</div>
            ) : null}
          </div>
        </section>
      </div>

      {result ? <TranscriptResult result={result} /> : null}

      <div className="grid gap-4 xl:grid-cols-[0.9fr,1.1fr]">
        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Article Status Hotspots</h2>
          </div>
          <div className="space-y-3 px-6 py-6">
            {topArticleCounts.map(([key, count]) => {
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
            {topArticleCounts.length === 0 ? (
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-8 text-center text-[14px] text-lookover-text-muted">
                No article count data is available from the voice auditor.
              </div>
            ) : null}
          </div>
        </section>

        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-6 py-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Detailed Runs</h2>
              <div className="text-[13px] text-lookover-text-muted">{featuredRecords.length} displayed from the bundled report</div>
            </div>
          </div>
          <div className="space-y-4 px-6 py-6">
            {featuredRecords.map((record) => (
              <details key={record.call_id} className="rounded-[20px] border border-lookover-border bg-white">
                <summary className="cursor-pointer list-none px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="lookover-label">Voice run</div>
                      <h3 className="mt-2 text-[18px] font-semibold tracking-[-0.03em] text-slate-900">{record.call_id}</h3>
                      <p className="mt-2 max-w-[64ch] text-[14px] leading-6 text-lookover-text-muted">
                        {record.scenario || record.risk_type || record.source_id}
                      </p>
                      <div className="mt-3 text-[13px] text-lookover-text-muted">{findingsSummary(record)}</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={getDispositionTone(record.disposition)}>{record.disposition.replaceAll("_", " ")}</Badge>
                      <Badge tone="neutral">{record.ai_disclosure_status.replaceAll("_", " ")}</Badge>
                    </div>
                  </div>
                </summary>
                <div className="border-t border-lookover-border px-5 py-5">
                  <div className="grid gap-5 xl:grid-cols-[0.92fr,1.08fr]">
                    <div className="space-y-4">
                      <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-4">
                        <div className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <div className="lookover-label">Started</div>
                            <div className="mt-2 text-[14px] text-slate-900">{formatCompactDate(record.started_at)}</div>
                          </div>
                          <div>
                            <div className="lookover-label">Applicability</div>
                            <div className="mt-2 text-[14px] text-slate-900">{record.applicability.replaceAll("_", " ")}</div>
                          </div>
                        </div>
                      </div>
                      <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-4">
                        <div className="lookover-label">Transcript Preview</div>
                        <div className="mt-3 space-y-3">
                          {record.transcript_preview.map((turn, index) => (
                            <div key={`${record.call_id}-${index}`} className="rounded-xl border border-white/70 bg-white px-3 py-3">
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
                            <div key={`${record.call_id}-timeline-${index}`} className="rounded-full border border-lookover-border bg-white px-3 py-2 text-[13px] text-slate-700">
                              <span className="font-medium">{item.event}</span> at {item.timestamp_seconds.toFixed(1)}s
                            </div>
                          ))}
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
                              <tr key={`${record.call_id}-finding-${index}`} className="border-b border-lookover-border/70 align-top last:border-b-0">
                                <td className="lookover-table-cell font-medium">Article {finding.article}</td>
                                <td className="lookover-table-cell">
                                  <Badge tone={getDispositionTone(finding.status)}>{finding.status.replaceAll("_", " ")}</Badge>
                                </td>
                                <td className="lookover-table-cell text-lookover-text-muted">{finding.severity}</td>
                                <td className="lookover-table-cell text-lookover-text-muted">{finding.reason}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>
              </details>
            ))}
            {featuredRecords.length === 0 ? (
              <div className="rounded-2xl border border-lookover-border bg-slate-50/70 px-4 py-12 text-center text-[15px] text-lookover-text-muted">
                The voice auditor report is unavailable. Start the `voice-auditor` service to populate this page.
              </div>
            ) : null}
          </div>
        </section>
      </div>
    </div>
  );
}
