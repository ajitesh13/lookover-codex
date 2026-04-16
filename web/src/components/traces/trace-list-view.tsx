"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ButtonLink } from "@/components/ui/button-link";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/lookover-format";
import type { ApiTraceSummary } from "@/lib/lookover-api";
import {
  deriveRootIntent,
  deriveTraceOutcome,
  formatDuration,
  formatRelativeTime,
  getToneFromStatus,
  normalizeStatus,
} from "@/lib/lookover-format";

const PAGE_SIZE = 25;

type Filters = {
  agentId: string;
  outcome: string;
  status: string;
  from: string;
  to: string;
};

const initialFilters: Filters = {
  agentId: "",
  outcome: "",
  status: "",
  from: "",
  to: "",
};

const actionButtonClass =
  "inline-flex h-10 items-center justify-center rounded-xl px-5 text-[13px] font-semibold transition";

function formatTraceIdLabel(traceId: string) {
  if (traceId.length <= 18) return traceId;
  return `${traceId.slice(0, 8)}...${traceId.slice(-6)}`;
}

function withinRange(value: string, from: string, to: string) {
  const timestamp = new Date(value).getTime();
  if (Number.isNaN(timestamp)) return true;
  if (from) {
    const fromTime = new Date(from).getTime();
    if (!Number.isNaN(fromTime) && timestamp < fromTime) return false;
  }
  if (to) {
    const toTime = new Date(`${to}T23:59:59`).getTime();
    if (!Number.isNaN(toTime) && timestamp > toTime) return false;
  }
  return true;
}

export function TraceListView({ traces }: { traces: ApiTraceSummary[] }) {
  const router = useRouter();
  const [draftFilters, setDraftFilters] = useState<Filters>(initialFilters);
  const [appliedFilters, setAppliedFilters] = useState<Filters>(initialFilters);
  const [page, setPage] = useState(1);

  const hasDraftFilters = Object.values(draftFilters).some(Boolean);
  const hasAppliedFilters = Object.values(appliedFilters).some(Boolean);

  const filtered = useMemo(() => {
    return traces.filter((trace) => {
      const outcome = deriveTraceOutcome(trace);
      return (
        (!appliedFilters.agentId ||
          trace.agent_id.toLowerCase().includes(appliedFilters.agentId.toLowerCase())) &&
        (!appliedFilters.outcome ||
          normalizeStatus(outcome).includes(appliedFilters.outcome.toLowerCase())) &&
        (!appliedFilters.status ||
          normalizeStatus(trace.status).includes(appliedFilters.status.toLowerCase())) &&
        withinRange(trace.updated_at || trace.created_at, appliedFilters.from, appliedFilters.to)
      );
    });
  }, [appliedFilters, traces]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const pageItems = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  function applyFilters() {
    setAppliedFilters(draftFilters);
    setPage(1);
  }

  function clearFilters() {
    setDraftFilters(initialFilters);
    setAppliedFilters(initialFilters);
    setPage(1);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="lookover-label">Trace history</div>
          <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.04em] text-slate-900">Recent agent runs</h1>
          <p className="mt-2 max-w-[60ch] text-[14px] leading-6 text-lookover-text-muted">
            Review trace activity, narrow results with lightweight filters, and open a run without changing the
            existing workflow.
          </p>
        </div>
        <ButtonLink href="/scans" tone="secondary">
          Open pre-run scans
        </ButtonLink>
      </div>

      <section className="lookover-card px-5 py-5">
        <div className="grid gap-4 xl:grid-cols-[1.2fr,0.9fr,0.9fr,0.8fr,0.8fr,auto]">
          <label className="grid gap-2">
            <span className="lookover-label">Agent ID</span>
            <input
              className="lookover-input"
              value={draftFilters.agentId}
              onChange={(event) => setDraftFilters((value) => ({ ...value, agentId: event.target.value }))}
              placeholder="Filter by agent ID"
            />
          </label>
          <label className="grid gap-2">
            <span className="lookover-label">Outcome</span>
            <select
              className="lookover-input"
              value={draftFilters.outcome}
              onChange={(event) => setDraftFilters((value) => ({ ...value, outcome: event.target.value }))}
            >
              <option value="">All outcomes</option>
              <option value="success">Success</option>
              <option value="failure">Failure</option>
              <option value="progress">In progress</option>
            </select>
          </label>
          <label className="grid gap-2">
            <span className="lookover-label">Status</span>
            <input
              className="lookover-input"
              value={draftFilters.status}
              onChange={(event) => setDraftFilters((value) => ({ ...value, status: event.target.value }))}
              placeholder="completed, running, blocked"
            />
          </label>
          <label className="grid gap-2">
            <span className="lookover-label">From</span>
            <input
              className="lookover-input"
              type="date"
              value={draftFilters.from}
              onChange={(event) => setDraftFilters((value) => ({ ...value, from: event.target.value }))}
            />
          </label>
          <label className="grid gap-2">
            <span className="lookover-label">To</span>
            <input
              className="lookover-input"
              type="date"
              value={draftFilters.to}
              onChange={(event) => setDraftFilters((value) => ({ ...value, to: event.target.value }))}
            />
          </label>
          <div className="flex items-end gap-2 xl:justify-end">
            <button
              type="button"
              className={cn(actionButtonClass, "bg-[#111113] text-white hover:bg-[#1b1b20]")}
              onClick={applyFilters}
            >
              Apply filters
            </button>
            {hasDraftFilters || hasAppliedFilters ? (
              <button
                type="button"
                className={cn(actionButtonClass, "border border-lookover-border bg-white px-4 text-slate-900 hover:bg-slate-50")}
                onClick={clearFilters}
              >
                Clear
              </button>
            ) : null}
          </div>
        </div>
      </section>

      <section className="lookover-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="min-w-full min-w-[920px]">
            <thead className="border-b border-lookover-border bg-slate-50/70">
              <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
                <th className="px-4 py-3.5">Trace ID</th>
                <th className="px-4 py-3.5">Agent ID</th>
                <th className="px-4 py-3.5">Root Intent</th>
                <th className="px-4 py-3.5">Status</th>
                <th className="px-4 py-3.5">Outcome</th>
                <th className="px-4 py-3.5">Spans</th>
                <th className="px-4 py-3.5">Started</th>
                <th className="px-4 py-3.5">Duration</th>
              </tr>
            </thead>
            <tbody>
              {pageItems.map((trace) => {
                const statusTone = getToneFromStatus(trace.status);
                const outcome = deriveTraceOutcome(trace);
                const outcomeTone = outcome === "Failure" ? "danger" : outcome === "In Progress" ? "warning" : "success";

                return (
                  <tr
                    key={trace.trace_id}
                    className="cursor-pointer border-b border-lookover-border/70 transition hover:bg-slate-50"
                    onClick={() => router.push(`/traces/${trace.trace_id}`)}
                  >
                    <td className="lookover-table-cell">
                      <Link
                        href={`/traces/${trace.trace_id}`}
                        className="inline-block max-w-[170px] truncate font-mono text-[14px] text-slate-500"
                        title={trace.trace_id}
                        onClick={(event) => event.stopPropagation()}
                      >
                        {formatTraceIdLabel(trace.trace_id)}
                      </Link>
                    </td>
                    <td className="lookover-table-cell">{trace.agent_id || "—"}</td>
                    <td className="lookover-table-cell max-w-[320px] text-lookover-text-muted">
                      <span className="block truncate" title={deriveRootIntent(trace)}>
                        {deriveRootIntent(trace)}
                      </span>
                    </td>
                    <td className="lookover-table-cell">
                      <Badge tone={statusTone === "danger" ? "danger" : statusTone === "warning" ? "warning" : "neutral"}>
                        {trace.status.toLowerCase()}
                      </Badge>
                    </td>
                    <td className="lookover-table-cell">
                      <Badge tone={outcomeTone}>{outcome.toLowerCase()}</Badge>
                    </td>
                    <td className="lookover-table-cell text-lookover-text-muted">{trace.span_count || "—"}</td>
                    <td className="lookover-table-cell text-lookover-text-muted">{formatRelativeTime(trace.created_at)}</td>
                    <td className="lookover-table-cell text-lookover-text-muted">
                      {formatDuration(trace.created_at, trace.updated_at)}
                    </td>
                  </tr>
                );
              })}

              {pageItems.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-12 text-center">
                    <div className="space-y-2">
                      <div className="text-[15px] font-medium text-slate-900">No traces match the current filters.</div>
                      <div className="text-[14px] text-lookover-text-muted">
                        Broaden the filters or clear them to return to the full trace history.
                      </div>
                      {hasAppliedFilters ? (
                        <div className="pt-2">
                          <button
                            type="button"
                            className={cn(actionButtonClass, "border border-lookover-border bg-white px-4 text-slate-900 hover:bg-slate-50")}
                            onClick={clearFilters}
                          >
                            Clear filters
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between px-5 py-4 text-[13px] text-lookover-text-muted">
          <span>{filtered.length} total traces</span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-lg border border-lookover-border px-3 py-2 transition hover:bg-slate-50 disabled:opacity-50"
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              disabled={currentPage <= 1}
            >
              Previous
            </button>
            <span>
              {currentPage} / {totalPages}
            </span>
            <button
              type="button"
              className="rounded-lg border border-lookover-border px-3 py-2 transition hover:bg-slate-50 disabled:opacity-50"
              onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              disabled={currentPage >= totalPages}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
