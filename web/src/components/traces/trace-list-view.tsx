"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ButtonLink } from "@/components/ui/button-link";
import { Badge } from "@/components/ui/badge";
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

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="lookover-label">Trace history</div>
          <h1 className="mt-2 text-[28px] font-semibold tracking-[-0.04em] text-slate-900">Recent agent runs</h1>
        </div>
        <ButtonLink href="/scans" tone="secondary">
          Open pre-run scans
        </ButtonLink>
      </div>

      <section className="lookover-card px-6 py-6">
        <div className="grid gap-4 xl:grid-cols-[1.2fr,0.9fr,0.9fr,0.8fr,0.8fr,auto]">
          <input
            className="lookover-input"
            value={draftFilters.agentId}
            onChange={(event) => setDraftFilters((value) => ({ ...value, agentId: event.target.value }))}
            placeholder="Filter by agent ID"
          />
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
          <input
            className="lookover-input"
            value={draftFilters.status}
            onChange={(event) => setDraftFilters((value) => ({ ...value, status: event.target.value }))}
            placeholder="completed, running, blocked"
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
          <button
            type="button"
            className="inline-flex h-11 items-center justify-center rounded-2xl bg-black px-5 text-sm font-medium text-white transition hover:bg-slate-900"
            onClick={applyFilters}
          >
            Apply filters
          </button>
        </div>
      </section>

      <section className="lookover-card overflow-hidden">
        <table className="min-w-full">
          <thead className="border-b border-lookover-border bg-slate-50/70">
            <tr className="text-left text-[12px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
              <th className="px-5 py-4">Trace ID</th>
              <th className="px-5 py-4">Agent ID</th>
              <th className="px-5 py-4">Root Intent</th>
              <th className="px-5 py-4">Status</th>
              <th className="px-5 py-4">Outcome</th>
              <th className="px-5 py-4">Spans</th>
              <th className="px-5 py-4">Started</th>
              <th className="px-5 py-4">Duration</th>
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
                      className="font-mono text-[15px] text-slate-500"
                      onClick={(event) => event.stopPropagation()}
                    >
                      {trace.trace_id}
                    </Link>
                  </td>
                  <td className="lookover-table-cell">{trace.agent_id || "—"}</td>
                  <td className="lookover-table-cell text-lookover-text-muted">{deriveRootIntent(trace)}</td>
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
                <td colSpan={8} className="px-5 py-12 text-center text-[15px] text-lookover-text-muted">
                  No traces match the current filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
        <div className="flex items-center justify-between px-6 py-5 text-[14px] text-lookover-text-muted">
          <span>{filtered.length} total traces</span>
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-xl border border-lookover-border px-3 py-2 transition hover:bg-slate-50 disabled:opacity-50"
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
              className="rounded-xl border border-lookover-border px-3 py-2 transition hover:bg-slate-50 disabled:opacity-50"
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
