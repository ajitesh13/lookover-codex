"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ButtonLink } from "@/components/ui/button-link";
import { Badge } from "@/components/ui/badge";
import type { ApiPreRunScan } from "@/lib/lookover-api";
import { formatCompactDate, getToneFromStatus } from "@/lib/lookover-format";

const PAGE_SIZE = 25;

export function ScanListView({ scans }: { scans: ApiPreRunScan[] }) {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(scans.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);

  const pageItems = useMemo(
    () => scans.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE),
    [currentPage, scans],
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="lookover-label">Pre-run scans</div>
          <h1 className="mt-2 text-[26px] font-semibold tracking-[-0.04em] text-slate-900">Run readiness history</h1>
        </div>
        <ButtonLink href="/traces" tone="secondary">
          Open trace history
        </ButtonLink>
      </div>

      <section className="lookover-card overflow-hidden">
        <table className="min-w-full">
          <thead className="border-b border-lookover-border bg-slate-50/70">
            <tr className="text-left text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
              <th className="px-4 py-3.5">Scan ID</th>
              <th className="px-4 py-3.5">Project</th>
              <th className="px-4 py-3.5">Strict</th>
              <th className="px-4 py-3.5">Outcome</th>
              <th className="px-4 py-3.5">Readiness</th>
              <th className="px-4 py-3.5">Frameworks</th>
              <th className="px-4 py-3.5">Findings</th>
              <th className="px-4 py-3.5">Created</th>
            </tr>
          </thead>
          <tbody>
            {pageItems.map((scan) => {
              const findings = scan.findings?.length ?? 0;
              const tone = getToneFromStatus(scan.strict_result);

              return (
                <tr
                  key={scan.scan_id}
                  className="cursor-pointer border-b border-lookover-border/70 transition hover:bg-slate-50"
                  onClick={() => router.push(`/pre-run/${scan.scan_id}`)}
                >
                  <td className="lookover-table-cell">
                    <Link
                      href={`/pre-run/${scan.scan_id}`}
                      className="font-mono text-[15px] text-slate-500"
                      onClick={(event) => event.stopPropagation()}
                    >
                      {scan.scan_id}
                    </Link>
                  </td>
                  <td className="lookover-table-cell text-lookover-text-muted">{scan.project_path}</td>
                  <td className="lookover-table-cell">
                    <Badge tone={scan.strict_mode ? "warning" : "neutral"}>
                      {scan.strict_mode ? "strict" : "advisory"}
                    </Badge>
                  </td>
                  <td className="lookover-table-cell">
                    <Badge tone={tone === "danger" ? "danger" : tone === "warning" ? "warning" : "success"}>
                      {scan.strict_result.toLowerCase()}
                    </Badge>
                  </td>
                  <td className="lookover-table-cell text-lookover-text-muted">
                    {Math.round(scan.readiness_score)}%
                  </td>
                  <td className="lookover-table-cell text-lookover-text-muted">{scan.frameworks.join(", ") || "—"}</td>
                  <td className="lookover-table-cell text-lookover-text-muted">{findings}</td>
                  <td className="lookover-table-cell text-lookover-text-muted">{formatCompactDate(scan.created_at)}</td>
                </tr>
              );
            })}
            {pageItems.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-5 py-12 text-center text-[15px] text-lookover-text-muted">
                  No pre-run scans are available yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
        <div className="flex items-center justify-between px-5 py-4 text-[13px] text-lookover-text-muted">
          <span>{scans.length} total scans</span>
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
