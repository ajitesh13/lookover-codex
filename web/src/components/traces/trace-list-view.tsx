"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiTraceSummary } from "@/lib/lookover-api";
import {
  deriveRootIntent,
  deriveTraceOutcome,
  formatDuration,
  formatRelativeTime,
  getRiskLabel,
  getToneFromStatus,
  normalizeStatus,
} from "@/lib/lookover-format";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import { ButtonLink } from "@/components/ui/button-link";
import shared from "@/components/ui/primitives.module.css";
import styles from "./traces.module.css";

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
    <div className={shared.section}>
      <PageHeader
        eyebrow="Traces"
        title="Recent agent runs"
        subtitle="Browse the latest traces, narrow by reviewer-friendly filters, and open any run into a full audit workspace."
        actions={<ButtonLink href="/scans">Open pre-run scans</ButtonLink>}
      />

      <SectionCard className={styles.filters}>
        <div className={styles.field}>
          <label htmlFor="agentId">Agent ID</label>
          <input
            id="agentId"
            value={draftFilters.agentId}
            onChange={(event) => setDraftFilters((value) => ({ ...value, agentId: event.target.value }))}
            placeholder="Filter by agent"
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="outcome">Outcome</label>
          <select
            id="outcome"
            value={draftFilters.outcome}
            onChange={(event) => setDraftFilters((value) => ({ ...value, outcome: event.target.value }))}
          >
            <option value="">All outcomes</option>
            <option value="success">Success</option>
            <option value="failure">Failure</option>
            <option value="progress">In progress</option>
          </select>
        </div>
        <div className={styles.field}>
          <label htmlFor="status">Status</label>
          <input
            id="status"
            value={draftFilters.status}
            onChange={(event) => setDraftFilters((value) => ({ ...value, status: event.target.value }))}
            placeholder="completed, running, blocked"
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="fromDate">From</label>
          <input
            id="fromDate"
            type="date"
            value={draftFilters.from}
            onChange={(event) => setDraftFilters((value) => ({ ...value, from: event.target.value }))}
          />
        </div>
        <div className={styles.field}>
          <label htmlFor="toDate">To</label>
          <input
            id="toDate"
            type="date"
            value={draftFilters.to}
            onChange={(event) => setDraftFilters((value) => ({ ...value, to: event.target.value }))}
          />
        </div>
        <div className={styles.filterAction}>
          <button type="button" className={`${shared.button} ${shared.buttonPrimary}`} onClick={applyFilters}>
            Apply filters
          </button>
        </div>
      </SectionCard>

      <SectionCard className={shared.tableShell}>
        <table className={shared.table}>
          <thead>
            <tr>
              <th>Trace ID</th>
              <th>Agent ID</th>
              <th>Root Intent</th>
              <th>Status</th>
              <th>Outcome</th>
              <th>Risk</th>
              <th>Spans</th>
              <th>Started</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody>
            {pageItems.map((trace) => {
              const statusTone = getToneFromStatus(trace.status);
              const outcome = deriveTraceOutcome(trace);
              const outcomeTone = outcome === "Failure" ? "danger" : outcome === "In Progress" ? "warning" : "success";
              const spanCount = trace.span_count;

              return (
                <tr
                  key={trace.trace_id}
                  className={shared.tableRowLink}
                  onClick={() => router.push(`/traces/${trace.trace_id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td>
                    <Link href={`/traces/${trace.trace_id}`} className={shared.mono} onClick={(event) => event.stopPropagation()}>
                      {trace.trace_id}
                    </Link>
                  </td>
                  <td>{trace.agent_id || "—"}</td>
                  <td className={shared.tableMeta}>{deriveRootIntent(trace)}</td>
                  <td>
                    <Badge tone={statusTone === "danger" ? "danger" : statusTone === "warning" ? "warning" : "neutral"}>
                      {trace.status}
                    </Badge>
                  </td>
                  <td>
                    <Badge tone={outcomeTone}>{outcome}</Badge>
                  </td>
                  <td className={shared.tableMeta}>{getRiskLabel(trace.overall_risk_score)}</td>
                  <td className={shared.tableMeta}>{spanCount || "—"}</td>
                  <td className={shared.tableMeta}>{formatRelativeTime(trace.created_at)}</td>
                  <td className={shared.tableMeta}>
                    {formatDuration(trace.created_at, trace.updated_at)}
                  </td>
                </tr>
              );
            })}
            {pageItems.length === 0 ? (
              <tr>
                <td colSpan={9}>
                  <div className={shared.emptyState}>
                    <div className={shared.emptyTitle}>No traces match the current filters</div>
                    <div className={shared.emptyBody}>
                      Clear or broaden the filters to inspect the latest agent runs.
                    </div>
                  </div>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
        <div className={shared.tableFooter}>
          <span>{filtered.length} total traces</span>
          <div className={shared.pagination}>
            <button
              type="button"
              className={`${shared.button} ${shared.buttonSecondary}`}
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
              className={`${shared.button} ${shared.buttonSecondary}`}
              onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
              disabled={currentPage >= totalPages}
            >
              Next
            </button>
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
