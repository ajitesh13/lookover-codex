"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  Copy,
  GitBranch,
  ShieldAlert,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ApiSpan, ApiTraceDetail, ShareMode } from "@/lib/lookover-api";
import {
  countFindingsByCategory,
  deriveTraceOutcome,
  formatCompactDate,
  formatDuration,
  getToneFromStatus,
  safeText,
  titleCase,
} from "@/lib/lookover-format";
import { cn } from "@/lib/lookover-format";

type TraceTreeNode = {
  span: ApiSpan;
  children: TraceTreeNode[];
};

function buildTree(spans: ApiSpan[]) {
  const byId = new Map<string, TraceTreeNode>();
  const roots: TraceTreeNode[] = [];

  spans.forEach((span) => byId.set(span.span_id, { span, children: [] }));

  byId.forEach((node) => {
    if (node.span.parent_span_id && byId.has(node.span.parent_span_id)) {
      byId.get(node.span.parent_span_id)?.children.push(node);
    } else {
      roots.push(node);
    }
  });

  return roots;
}

function findingCountsForSpan(detail: ApiTraceDetail, spanId: string) {
  return detail.findings
    .filter((finding) => finding.span_id === spanId)
    .reduce(
      (accumulator, finding) => {
        const tone = getToneFromStatus(finding.status);
        if (tone === "danger") accumulator.violations += 1;
        else if (tone === "warning") accumulator.gaps += 1;
        else accumulator.covered += 1;
        return accumulator;
      },
      { violations: 0, gaps: 0, covered: 0 },
    );
}

function flattenTree(nodes: TraceTreeNode[], depth = 0): Array<{ node: TraceTreeNode; depth: number }> {
  return nodes.flatMap((node) => [{ node, depth }, ...flattenTree(node.children, depth + 1)]);
}

function getSpanIcon(span: ApiSpan) {
  const normalized = `${span.event_type} ${span.name}`.toLowerCase();
  if (normalized.includes("decision") || normalized.includes("supervisor")) {
    return { Icon: GitBranch, className: "bg-rose-50 text-rose-500" };
  }
  return { Icon: Wrench, className: "bg-sky-50 text-sky-600" };
}

function extractRoutingDecision(span: ApiSpan) {
  const payload = span.payload ?? {};
  return (
    safeText(
      payload.route_decision ??
        payload.routing_decision ??
        payload.llm_output ??
        payload.message ??
        payload.output,
    ) || safeText(payload)
  );
}

function extractStateChanges(span: ApiSpan) {
  const payload = span.payload ?? {};
  if (payload.state_changes) return safeText(payload.state_changes);
  if (payload.next_worker) return safeText({ next_worker: payload.next_worker });
  return safeText(payload);
}

function ShareActions({ traceId }: { traceId: string }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState("");
  const [loadingMode, setLoadingMode] = useState<ShareMode | null>(null);

  async function createShare(mode: ShareMode) {
    setLoadingMode(mode);
    setStatus("");
    try {
      const response = await fetch(`/api/traces/${traceId}/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      const payload = (await response.json()) as { url?: string; error?: string };
      if (!response.ok || !payload.url) {
        setStatus(payload.error || "Share link could not be created.");
        return;
      }
      await navigator.clipboard.writeText(payload.url);
      setStatus(mode === "audit_log_only" ? "Copied trace-only link." : "Copied compliance share link.");
      setOpen(false);
    } catch {
      setStatus("Share link could not be created.");
    } finally {
      setLoadingMode(null);
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        className="inline-flex h-12 items-center gap-2 rounded-2xl border border-lookover-border bg-white px-4 text-sm font-medium text-slate-900 transition hover:bg-slate-50"
        onClick={() => setOpen((value) => !value)}
      >
        <Sparkles className="h-4 w-4" />
        Share
      </button>
      {open ? (
        <div className="absolute right-0 top-14 z-20 w-[270px] rounded-[20px] border border-lookover-border bg-white p-2 shadow-lookover-card">
          <button
            type="button"
            className="flex w-full flex-col items-start rounded-2xl px-4 py-3 text-left transition hover:bg-slate-50"
            onClick={() => createShare("audit_log_plus_evaluation")}
            disabled={loadingMode !== null}
          >
            <span className="text-sm font-semibold text-slate-900">With compliance</span>
            <span className="mt-1 text-[13px] leading-5 text-lookover-text-muted">
              Includes violations, gaps, and covered findings.
            </span>
          </button>
          <button
            type="button"
            className="flex w-full flex-col items-start rounded-2xl px-4 py-3 text-left transition hover:bg-slate-50"
            onClick={() => createShare("audit_log_only")}
            disabled={loadingMode !== null}
          >
            <span className="text-sm font-semibold text-slate-900">Without compliance</span>
            <span className="mt-1 text-[13px] leading-5 text-lookover-text-muted">
              Only the trace tree and node detail.
            </span>
          </button>
        </div>
      ) : null}
      {status ? <div className="mt-2 text-[13px] text-lookover-text-muted">{status}</div> : null}
    </div>
  );
}

function SummaryCounter({
  label,
  count,
  tone,
  onClick,
}: {
  label: string;
  count: number;
  tone: "danger" | "warning" | "success";
  onClick: () => void;
}) {
  const toneClass =
    tone === "danger"
      ? "border-rose-200 bg-rose-50/50 text-rose-400"
      : tone === "warning"
        ? "border-amber-300 bg-amber-50/60 text-amber-600"
        : "border-emerald-300 bg-emerald-50/60 text-emerald-600";
  const Icon = tone === "danger" ? AlertTriangle : tone === "warning" ? ShieldAlert : CheckCircle2;

  return (
    <button
      type="button"
      className={cn(
        "flex h-[78px] items-center justify-between rounded-[22px] border px-6 text-left transition hover:bg-white",
        toneClass,
      )}
      onClick={onClick}
    >
      <div className="flex items-center gap-4">
        <span className="inline-flex h-8 w-1 rounded-full bg-current/90" />
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-current/20 bg-white/60">
          <Icon className="h-4 w-4" />
        </span>
        <span className="text-[16px] font-medium">{label}</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="rounded-xl border border-current/20 bg-white/70 px-3 py-1.5 text-[14px] font-medium">
          {count}
        </span>
        <ChevronDown className="h-4 w-4 opacity-60" />
      </div>
    </button>
  );
}

function FindingPanel({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "danger" | "warning" | "success";
  items: ApiTraceDetail["findings"];
}) {
  const toneClasses =
    tone === "danger"
      ? "border-rose-200 bg-rose-50/40"
      : tone === "warning"
        ? "border-amber-300 bg-amber-50/40"
        : "border-emerald-300 bg-emerald-50/40";

  return (
    <section className={cn("rounded-[22px] border p-4", toneClasses)}>
      <div className="flex items-center justify-between">
        <h3 className="text-[16px] font-semibold text-slate-900">{title}</h3>
        <span className="rounded-xl border border-white/60 bg-white/80 px-2.5 py-1 text-[13px] font-medium text-slate-500">
          {items.length}
        </span>
      </div>
      <div className="mt-4 space-y-3">
        {items.length === 0 ? (
          <div className="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 text-[14px] text-lookover-text-muted">
            No findings in this section for the selected trace.
          </div>
        ) : (
          items.slice(0, 3).map((finding) => (
            <div key={finding.id} className="rounded-2xl border border-white/70 bg-white/80 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
                <span>{finding.framework}</span>
                <span>{finding.control_id}</span>
                {finding.span_id ? <span>span:{finding.span_id.slice(0, 8)}</span> : null}
              </div>
              <div className="mt-2 text-[15px] font-medium leading-6 text-slate-900">{finding.title}</div>
              <div className="mt-2 text-[13px] leading-6 text-lookover-text-muted">
                {finding.reasoning || finding.remediation}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

export function TraceWorkspace({
  detail,
  readOnly = false,
  shareMode = "audit_log_plus_evaluation",
}: {
  detail: ApiTraceDetail;
  readOnly?: boolean;
  shareMode?: ShareMode;
}) {
  const tree = useMemo(() => buildTree(detail.spans), [detail.spans]);
  const flattened = useMemo(() => flattenTree(tree), [tree]);
  const [selectedSpanId, setSelectedSpanId] = useState("");
  const [showFindings, setShowFindings] = useState(shareMode !== "audit_log_only");
  const selectedSpan = detail.spans.find((item) => item.span_id === selectedSpanId) ?? null;
  const selectedEvidence = detail.evidence.filter((item) => item.span_id === selectedSpan?.span_id);
  const grouped = countFindingsByCategory(detail.findings);
  const showCompliance = shareMode !== "audit_log_only";
  const outcome = deriveTraceOutcome(detail.trace);

  const groupedFindings = {
    violations: detail.findings.filter((item) => getToneFromStatus(item.status) === "danger"),
    gaps: detail.findings.filter((item) => getToneFromStatus(item.status) === "warning"),
    covered: detail.findings.filter((item) => getToneFromStatus(item.status) === "neutral"),
  };

  async function copyTraceId() {
    await navigator.clipboard.writeText(detail.trace.trace_id);
  }

  return (
    <div className="space-y-8">
      {readOnly ? (
        <div className="lookover-card-tight px-6 py-4 text-[14px] text-lookover-text-muted">
          Shared review mode is active. Navigation and trace inspection stay available, while editing actions remain disabled.
        </div>
      ) : null}

      <section className="lookover-card px-8 py-7">
        <div className="flex flex-col gap-7">
          <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-4 text-[15px] text-lookover-text-muted">
                <Link href="/traces" className="inline-flex items-center gap-2 transition hover:text-slate-900">
                  <ArrowLeft className="h-4 w-4" />
                  <span>Traces</span>
                </Link>
                <span>/</span>
                <span className="font-mono text-[18px] text-slate-900">{detail.trace.trace_id}</span>
                <button
                  type="button"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-lookover-border text-slate-400 transition hover:bg-slate-50 hover:text-slate-700"
                  onClick={copyTraceId}
                >
                  <Copy className="h-4 w-4" />
                </button>
                <Badge tone="success" className="text-[13px] capitalize">
                  {detail.trace.status.toLowerCase()}
                </Badge>
                <Badge tone={outcome === "In Progress" ? "warning" : "danger"} className="text-[13px]">
                  {outcome.toLowerCase()}
                </Badge>
              </div>

              <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4 xl:gap-10">
                <div>
                  <div className="text-[14px] text-lookover-text-muted">Agent</div>
                  <div className="mt-2 text-[18px] font-medium text-slate-900">{detail.trace.agent_id}</div>
                </div>
                <div>
                  <div className="text-[14px] text-lookover-text-muted">Started</div>
                  <div className="mt-2 text-[18px] font-medium text-slate-900">{formatCompactDate(detail.trace.created_at)}</div>
                </div>
                <div>
                  <div className="text-[14px] text-lookover-text-muted">Duration</div>
                  <div className="mt-2 text-[18px] font-medium text-slate-900">
                    {formatDuration(detail.trace.created_at, detail.trace.updated_at)}
                  </div>
                </div>
                <div>
                  <div className="text-[14px] text-lookover-text-muted">Spans</div>
                  <div className="mt-2 text-[18px] font-medium text-slate-900">{detail.spans.length}</div>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 self-start">
              {!readOnly ? <ShareActions traceId={detail.trace.trace_id} /> : null}
              <button
                type="button"
                className="inline-flex h-12 items-center gap-2 rounded-2xl border border-lookover-border bg-white px-4 text-sm font-medium text-slate-900 transition hover:bg-slate-50"
              >
                <Sparkles className="h-4 w-4" />
                AIBOM
              </button>
            </div>
          </div>

          {showCompliance ? (
            <>
              <div className="grid gap-4 xl:grid-cols-3">
                <SummaryCounter label="Violations" count={grouped.violations} tone="danger" onClick={() => setShowFindings((value) => !value)} />
                <SummaryCounter label="Gaps" count={grouped.gaps} tone="warning" onClick={() => setShowFindings((value) => !value)} />
                <SummaryCounter label="Covered" count={grouped.covered} tone="success" onClick={() => setShowFindings((value) => !value)} />
              </div>

              {showFindings ? (
                <div className="grid gap-4 xl:grid-cols-3">
                  <FindingPanel title="Violations" tone="danger" items={groupedFindings.violations} />
                  <FindingPanel title="Gaps" tone="warning" items={groupedFindings.gaps} />
                  <FindingPanel title="Covered" tone="success" items={groupedFindings.covered} />
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      </section>

      <div className={cn("grid gap-5", selectedSpan ? "xl:grid-cols-[1.55fr,0.9fr]" : "grid-cols-1")}>
        <section className="lookover-card overflow-hidden">
          <div className="px-6 py-6">
            {flattened.map(({ node, depth }) => {
              const counts = findingCountsForSpan(detail, node.span.span_id);
              const isSelected = selectedSpanId === node.span.span_id;
              const { Icon, className } = getSpanIcon(node.span);
              const totalFlags = counts.violations + counts.gaps + counts.covered;

              return (
                <div
                  key={node.span.span_id}
                  className={cn(
                    "flex items-center gap-3 rounded-[22px] px-4 py-3 transition",
                    isSelected ? "bg-black text-white shadow-sm" : "hover:bg-slate-50",
                  )}
                  style={{ paddingLeft: `${depth * 28 + 16}px` }}
                >
                  <span className={cn("h-2.5 w-2.5 rounded-full", isSelected ? "bg-white/60" : "bg-slate-300")} />
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 items-center gap-4 text-left"
                    onClick={() => {
                      setSelectedSpanId(node.span.span_id);
                      setShowFindings(false);
                    }}
                  >
                    <span className={cn("inline-flex h-12 w-12 items-center justify-center rounded-2xl", className)}>
                      <Icon className="h-5 w-5" />
                    </span>
                    <span className="truncate text-[18px] font-medium tracking-[-0.02em]">
                      {node.span.name || titleCase(node.span.event_type)}
                    </span>
                  </button>
                  {showCompliance ? (
                    <div className="ml-auto flex items-center gap-3">
                      {counts.violations > 0 ? (
                        <span
                          className={cn(
                            "inline-flex min-w-[34px] items-center justify-center rounded-full border px-2 py-1 text-[14px] font-medium",
                            isSelected
                              ? "border-rose-300/40 bg-rose-400/10 text-rose-200"
                              : "border-rose-200 bg-rose-50 text-rose-500",
                          )}
                        >
                          {counts.violations}
                        </span>
                      ) : null}
                      {totalFlags > 0 ? (
                        <span
                          className={cn(
                            "inline-flex min-w-[40px] items-center justify-center rounded-full border px-2 py-1 text-[14px] font-medium",
                            isSelected
                              ? "border-amber-300/40 bg-amber-400/10 text-amber-200"
                              : "border-amber-300 bg-amber-50 text-amber-600",
                          )}
                        >
                          {totalFlags}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </section>

        {selectedSpan ? (
          <section className="lookover-card px-7 py-6">
            <div className="flex items-start justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone="danger" className="text-[14px]">
                  {titleCase(selectedSpan.event_type)} / Routing
                </Badge>
                <span className="rounded-xl bg-indigo-50 px-3 py-1.5 font-mono text-[15px] text-indigo-900">
                  {selectedSpan.name}
                </span>
              </div>
              <button
                type="button"
                className="text-slate-400 transition hover:text-slate-700"
                onClick={() => setSelectedSpanId("")}
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-8 grid gap-8 sm:grid-cols-2">
              <div>
                <div className="lookover-label">Start time</div>
                <div className="mt-3 text-[18px] font-medium tracking-[-0.02em] text-slate-900">
                  {formatCompactDate(selectedSpan.start_time)}
                </div>
              </div>
              <div>
                <div className="lookover-label">Duration</div>
                <div className="mt-3 text-[18px] font-medium tracking-[-0.02em] text-slate-900">
                  {formatDuration(selectedSpan.start_time, selectedSpan.end_time)}
                </div>
              </div>
              <div>
                <div className="lookover-label">Outcome</div>
                <div className="mt-3">
                  <Badge tone={getToneFromStatus(selectedSpan.status) === "danger" ? "danger" : "success"} className="text-[13px]">
                    {selectedSpan.status.toLowerCase()}
                  </Badge>
                </div>
              </div>
            </div>

            <div className="mt-8 border-t border-lookover-border pt-7">
              <div className="lookover-label">Routing decision (LLM output)</div>
              <div className="mt-4 rounded-[20px] bg-indigo-50 px-5 py-4 text-[15px] leading-8 text-slate-600">
                {extractRoutingDecision(selectedSpan)}
              </div>
            </div>

            <div className="mt-8 border-t border-lookover-border pt-7">
              <div className="lookover-label">Agent state changes from this node</div>
              <pre className="mt-4 overflow-x-auto rounded-[20px] bg-indigo-50 px-5 py-4 font-mono text-[14px] leading-8 text-slate-600">
                {extractStateChanges(selectedSpan)}
              </pre>
            </div>

            <div className="mt-8 border-t border-lookover-border pt-7">
              <div className="lookover-label">Raw evidence</div>
              {selectedEvidence.length === 0 ? (
                <div className="mt-4 rounded-[20px] border border-dashed border-lookover-border px-5 py-4 text-[14px] text-lookover-text-muted">
                  No evidence rows were attached to this node.
                </div>
              ) : (
                <div className="mt-4 space-y-3">
                  {selectedEvidence.map((item) => (
                    <div key={item.id} className="rounded-[20px] border border-lookover-border bg-slate-50 px-5 py-4">
                      <div className="text-[13px] font-medium uppercase tracking-[0.14em] text-lookover-text-muted">
                        {item.source} · {item.field_name}
                      </div>
                      <pre className="mt-3 overflow-x-auto font-mono text-[13px] leading-7 text-slate-600">
                        {safeText(item.value)}
                      </pre>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
