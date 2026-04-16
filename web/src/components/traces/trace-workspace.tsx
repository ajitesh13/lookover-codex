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
import { CollapsibleJson } from "@/components/ui/collapsible-json";
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

function getSpanMetadata(span: ApiSpan) {
  const payload = span.payload ?? {};
  const extra = payload.extra;
  if (!extra || typeof extra !== "object" || Array.isArray(extra)) return {};
  const metadata = (extra as Record<string, unknown>).metadata;
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) return {};
  return metadata as Record<string, unknown>;
}

function getLanggraphNode(span: ApiSpan) {
  const payload = span.payload ?? {};
  return (
    safeText(payload.node_name ?? payload.nodeName ?? getSpanMetadata(span).langgraph_node).trim() || ""
  );
}

function isGenericSpanName(value?: string | null) {
  const normalized = String(value ?? "").trim().toLowerCase();
  return !normalized || ["chain_start", "chain_end", "chain_error", "llm_start", "llm_end", "llm_error"].includes(normalized);
}

function inferSpanKind(span: ApiSpan) {
  const eventType = span.event_type.toUpperCase();
  const nodeName = getLanggraphNode(span).toLowerCase();

  if (eventType.startsWith("TRACE_")) return "TRACE";
  if (eventType.includes("ERROR") || getToneFromStatus(span.status) === "danger") return "ERROR";
  if (eventType === "TOOL_CALL" || eventType.startsWith("TOOL_")) return "TOOL_CALL";
  if (eventType === "HUMAN_HANDOFF") return "HUMAN_HANDOFF";
  if (eventType === "DECISION") return "DECISION";
  if (eventType === "MODEL_INFERENCE") return "MODEL_INFERENCE";
  if (eventType.startsWith("LLM_")) {
    return nodeName.includes("supervisor") || nodeName.includes("router") || nodeName.includes("planner")
      ? "DECISION"
      : "MODEL_INFERENCE";
  }
  if (eventType.startsWith("CHAIN_")) {
    return nodeName ? "NODE" : "TRACE";
  }
  return eventType;
}

function getSpanLabel(span: ApiSpan) {
  const payload = span.payload ?? {};
  const kind = inferSpanKind(span);
  const nodeName = getLanggraphNode(span);
  const serialized = payload.serialized;
  const serializedName =
    serialized && typeof serialized === "object" && !Array.isArray(serialized)
      ? safeText((serialized as Record<string, unknown>).name)
      : "";
  const toolName = safeText(payload.tool_name ?? serializedName).trim();

  if (String(span.name).toUpperCase() === "DECISION") return "DECISION";
  if (kind === "TOOL_CALL" && toolName) return toolName;
  if (kind === "DECISION" && isGenericSpanName(span.name)) return "DECISION";
  if (nodeName) return nodeName;
  if (span.name && !isGenericSpanName(span.name)) return span.name;
  return titleCase(kind);
}

function getSpanTone(span: ApiSpan) {
  const kind = inferSpanKind(span);
  if (kind === "ERROR") return "danger" as const;
  if (kind === "DECISION") return "warning" as const;
  if (kind === "TOOL_CALL" || kind === "MODEL_INFERENCE") return "success" as const;
  return "neutral" as const;
}

function shouldDisplaySpan(span: ApiSpan) {
  const eventType = span.event_type.toUpperCase();
  if (eventType.startsWith("TRACE_")) return false;
  if (eventType === "CHAIN_END" || eventType === "LLM_END" || eventType === "TOOL_END") return false;
  if (eventType === "CHAIN_START" && !getLanggraphNode(span)) return false;
  return true;
}

function getSpanIcon(span: ApiSpan) {
  const kind = inferSpanKind(span);
  if (kind === "ERROR") {
    return { Icon: AlertTriangle, className: "bg-rose-50 text-rose-500" };
  }
  if (kind === "DECISION") {
    return { Icon: GitBranch, className: "bg-rose-50 text-rose-500" };
  }
  if (kind === "MODEL_INFERENCE") {
    return { Icon: Sparkles, className: "bg-violet-50 text-violet-600" };
  }
  return { Icon: Wrench, className: "bg-sky-50 text-sky-600" };
}

function extractRoutingDecision(span: ApiSpan) {
  const payload = span.payload ?? {};
  return (
    safeText(
      payload.model_output ??
        payload.route_decision ??
        payload.routing_decision ??
        payload.response ??
        payload.llm_output ??
        payload.prompts ??
        payload.message ??
        payload.output ??
        payload.error,
    ) || safeText(payload)
  );
}

function extractStateChanges(span: ApiSpan) {
  const payload = span.payload ?? {};
  if (payload.state_after) return payload.state_after;
  if (payload.state_changes) return payload.state_changes;
  if (payload.outputs) return payload.outputs;
  if (payload.inputs) return payload.inputs;
  if (payload.next_worker) return { next_worker: payload.next_worker };
  return payload;
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
        className="inline-flex h-10 items-center gap-2 rounded-xl border border-lookover-border bg-white px-4 text-[13px] font-semibold text-slate-900 transition hover:bg-slate-50"
        onClick={() => setOpen((value) => !value)}
      >
        <Sparkles className="h-4 w-4" />
        Share
      </button>
      {open ? (
        <div className="absolute right-0 top-12 z-20 w-[270px] rounded-[14px] border border-lookover-border bg-white p-2 shadow-lookover-card">
          <button
            type="button"
            className="flex w-full flex-col items-start rounded-xl px-4 py-3 text-left transition hover:bg-slate-50"
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
            className="flex w-full flex-col items-start rounded-xl px-4 py-3 text-left transition hover:bg-slate-50"
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
      ? "border-rose-200 bg-rose-50/70 text-rose-500"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50/80 text-amber-700"
        : "border-emerald-200 bg-emerald-50/80 text-emerald-700";
  const Icon = tone === "danger" ? AlertTriangle : tone === "warning" ? ShieldAlert : CheckCircle2;

  return (
    <button
      type="button"
      className={cn(
        "flex h-[70px] items-center justify-between rounded-[16px] border px-5 text-left transition hover:bg-white",
        toneClass,
      )}
      onClick={onClick}
    >
      <div className="flex items-center gap-4">
        <span className="inline-flex h-8 w-1 rounded-full bg-current/90" />
        <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-current/20 bg-white/70">
          <Icon className="h-4 w-4" />
        </span>
        <span className="text-[15px] font-medium">{label}</span>
      </div>
      <div className="flex items-center gap-4">
        <span className="rounded-lg border border-current/20 bg-white/75 px-3 py-1.5 text-[13px] font-medium">
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
        ? "border-amber-200 bg-amber-50/40"
        : "border-emerald-200 bg-emerald-50/40";

  return (
    <section className={cn("rounded-[16px] border p-4", toneClasses)}>
      <div className="flex items-center justify-between">
        <h3 className="text-[16px] font-semibold text-slate-900">{title}</h3>
        <span className="rounded-lg border border-white/60 bg-white/80 px-2.5 py-1 text-[12px] font-medium text-slate-500">
          {items.length}
        </span>
      </div>
      <div className="mt-4 space-y-3">
        {items.length === 0 ? (
          <div className="rounded-xl border border-white/70 bg-white/80 px-4 py-4 text-[14px] text-lookover-text-muted">
            No findings in this section for the selected trace.
          </div>
        ) : (
          items.slice(0, 3).map((finding) => (
            <div key={finding.id} className="rounded-xl border border-white/70 bg-white/80 px-4 py-3">
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

function StepSection({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded-[16px] border border-lookover-border bg-slate-50/65 p-4">
      <div>
        <div className="lookover-label">{eyebrow}</div>
        <h3 className="mt-2 text-[15px] font-semibold tracking-[-0.02em] text-slate-900">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function StepFindingCard({ finding }: { finding: ApiTraceDetail["findings"][number] }) {
  const tone = getToneFromStatus(finding.status);
  const toneClass =
    tone === "danger"
      ? "border-rose-200 bg-rose-50/70"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50/70"
        : "border-emerald-200 bg-emerald-50/70";

  return (
    <div className={cn("rounded-[14px] border px-4 py-4", toneClass)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={tone === "danger" ? "danger" : tone === "warning" ? "warning" : "success"}>
              {finding.status.toLowerCase()}
            </Badge>
            <Badge tone="neutral">{finding.framework}</Badge>
            <Badge tone="neutral">{finding.control_id}</Badge>
            {finding.severity ? <Badge tone={tone === "danger" ? "danger" : "warning"}>{finding.severity.toLowerCase()}</Badge> : null}
          </div>
          <div className="text-[15px] font-semibold leading-6 text-slate-900">{finding.title}</div>
        </div>
      </div>
      <div className="mt-3 text-[13px] leading-6 text-lookover-text-muted">
        {finding.reasoning || finding.remediation}
      </div>
    </div>
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
  const visibleSpans = useMemo(() => {
    const filtered = detail.spans.filter(shouldDisplaySpan);
    return filtered.length > 0 ? filtered : detail.spans;
  }, [detail.spans]);
  const tree = useMemo(() => buildTree(visibleSpans), [visibleSpans]);
  const flattened = useMemo(() => flattenTree(tree), [tree]);
  const [selectedSpanId, setSelectedSpanId] = useState("");
  const [showFindings, setShowFindings] = useState(shareMode !== "audit_log_only");
  const selectedSpan = visibleSpans.find((item) => item.span_id === selectedSpanId) ?? null;
  const selectedEvidence = detail.evidence.filter((item) => item.span_id === selectedSpan?.span_id);
  const selectedFindings = detail.findings.filter((item) => item.span_id === selectedSpan?.span_id);
  const grouped = countFindingsByCategory(detail.findings);
  const showCompliance = shareMode !== "audit_log_only";
  const outcome = deriveTraceOutcome(detail.trace);

  const groupedFindings = {
    violations: detail.findings.filter((item) => getToneFromStatus(item.status) === "danger"),
    gaps: detail.findings.filter((item) => getToneFromStatus(item.status) === "warning"),
    covered: detail.findings.filter((item) => getToneFromStatus(item.status) === "neutral"),
  };
  const selectedFindingGroups = {
    violations: selectedFindings.filter((item) => getToneFromStatus(item.status) === "danger"),
    gaps: selectedFindings.filter((item) => getToneFromStatus(item.status) === "warning"),
    covered: selectedFindings.filter((item) => getToneFromStatus(item.status) === "neutral"),
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

      <section className="lookover-card px-6 py-6">
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
                  className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-lookover-border text-slate-400 transition hover:bg-slate-50 hover:text-slate-700"
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
                  <div className="mt-2 text-[17px] font-medium text-slate-900">{detail.trace.agent_id}</div>
                </div>
                <div>
                  <div className="text-[14px] text-lookover-text-muted">Started</div>
                  <div className="mt-2 text-[17px] font-medium text-slate-900">{formatCompactDate(detail.trace.created_at)}</div>
                </div>
                <div>
                  <div className="text-[14px] text-lookover-text-muted">Duration</div>
                  <div className="mt-2 text-[17px] font-medium text-slate-900">
                    {formatDuration(detail.trace.created_at, detail.trace.updated_at)}
                  </div>
                </div>
                <div>
                  <div className="text-[14px] text-lookover-text-muted">Spans</div>
                  <div className="mt-2 text-[17px] font-medium text-slate-900">{detail.spans.length}</div>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-3 self-start">
              {!readOnly ? <ShareActions traceId={detail.trace.trace_id} /> : null}
              <button
                type="button"
                className="inline-flex h-10 items-center gap-2 rounded-xl border border-lookover-border bg-white px-4 text-[13px] font-semibold text-slate-900 transition hover:bg-slate-50"
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

      <div
        className={cn(
          "grid gap-4",
          selectedSpan ? "xl:grid-cols-2" : "grid-cols-1",
        )}
      >
        <section className="lookover-card min-w-0 overflow-hidden">
          <div className="px-5 py-5">
            {flattened.map(({ node, depth }) => {
              const counts = findingCountsForSpan(detail, node.span.span_id);
              const isSelected = selectedSpanId === node.span.span_id;
              const { Icon, className } = getSpanIcon(node.span);
              const totalFlags = counts.violations + counts.gaps + counts.covered;

              return (
                <div
                  key={node.span.span_id}
                  className={cn(
                    "flex items-center gap-3 rounded-[16px] border border-transparent px-4 py-2.5 transition",
                    isSelected ? "border-black bg-black text-white shadow-sm" : "hover:border-lookover-border hover:bg-slate-50",
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
                    <span className={cn("inline-flex h-10 w-10 items-center justify-center rounded-xl", className)}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="truncate text-[15px] font-medium tracking-[-0.02em]">
                      {getSpanLabel(node.span)}
                    </span>
                  </button>
                  {showCompliance ? (
                    <div className="ml-auto flex items-center gap-3">
                      {counts.violations > 0 ? (
                        <span
                          className={cn(
                            "inline-flex min-w-[34px] items-center justify-center rounded-md border px-2 py-1 text-[13px] font-medium",
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
                            "inline-flex min-w-[40px] items-center justify-center rounded-md border px-2 py-1 text-[13px] font-medium",
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
          <section className="lookover-card min-w-0 overflow-hidden px-6 py-5 xl:max-h-[calc(100vh-9.5rem)] xl:overflow-y-auto xl:overscroll-contain">
            <div className="flex items-start justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone={getSpanTone(selectedSpan)} className="text-[14px]">
                  {titleCase(inferSpanKind(selectedSpan))}
                </Badge>
                <span className="rounded-lg bg-indigo-50 px-3 py-1.5 font-mono text-[14px] text-indigo-900">
                  {getSpanLabel(selectedSpan)}
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

            <div className="mt-8 space-y-4 border-t border-lookover-border pt-7">
              <StepSection eyebrow="Step output" title="Routing decision (LLM output)">
                <CollapsibleJson
                  value={extractRoutingDecision(selectedSpan)}
                  className="border-indigo-100 bg-indigo-50/80"
                />
              </StepSection>

              <StepSection eyebrow="Step output" title="Agent state changes from this node">
                <CollapsibleJson
                  value={extractStateChanges(selectedSpan)}
                  className="border-indigo-100 bg-indigo-50/80"
                />
              </StepSection>

              <StepSection eyebrow="Screening" title="Controls evaluated on this step">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-rose-200 bg-rose-50/70 px-4 py-3">
                    <div className="lookover-label">Violations</div>
                    <div className="mt-2 text-[24px] font-semibold leading-none tracking-[-0.03em] text-rose-600">
                      {selectedFindingGroups.violations.length}
                    </div>
                  </div>
                  <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3">
                    <div className="lookover-label">Gaps</div>
                    <div className="mt-2 text-[24px] font-semibold leading-none tracking-[-0.03em] text-amber-600">
                      {selectedFindingGroups.gaps.length}
                    </div>
                  </div>
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
                    <div className="lookover-label">Covered</div>
                    <div className="mt-2 text-[24px] font-semibold leading-none tracking-[-0.03em] text-emerald-600">
                      {selectedFindingGroups.covered.length}
                    </div>
                  </div>
                </div>
                {selectedFindings.length === 0 ? (
                  <div className="rounded-[14px] border border-dashed border-lookover-border bg-white/70 px-4 py-4 text-[14px] text-lookover-text-muted">
                    No screening findings were attached to this agent step.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {selectedFindings.map((finding) => (
                      <StepFindingCard key={finding.id} finding={finding} />
                    ))}
                  </div>
                )}
              </StepSection>

              <StepSection eyebrow="Evidence" title="Raw evidence">
                {selectedEvidence.length === 0 ? (
                  <div className="rounded-[14px] border border-dashed border-lookover-border bg-white/70 px-4 py-4 text-[14px] text-lookover-text-muted">
                    No evidence rows were attached to this node.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {selectedEvidence.map((item) => (
                      <div key={item.id} className="min-w-0 rounded-[14px] border border-lookover-border bg-white/80 px-4 py-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone="neutral">{item.source}</Badge>
                          <span className="text-[13px] font-medium text-slate-900">{item.field_name}</span>
                        </div>
                        <CollapsibleJson value={item.value} className="mt-3 bg-slate-50/80" defaultExpanded={false} />
                      </div>
                    ))}
                  </div>
                )}
              </StepSection>
            </div>
          </section>
        ) : null}
      </div>
    </div>
  );
}
