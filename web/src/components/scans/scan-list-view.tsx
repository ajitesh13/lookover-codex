"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiPreRunScan } from "@/lib/lookover-api";
import { formatCompactDate, getToneFromStatus } from "@/lib/lookover-format";
import { Badge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button-link";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import shared from "@/components/ui/primitives.module.css";

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
    <div className={shared.section}>
      <PageHeader
        eyebrow="Scans"
        title="Pre-run scan history"
        subtitle="Inspect readiness, strict-mode outcomes, and governance evidence before an agent run reaches production."
        actions={<ButtonLink href="/traces">Open trace history</ButtonLink>}
      />

      <SectionCard className={shared.tableShell}>
        <table className={shared.table}>
          <thead>
            <tr>
              <th>Scan ID</th>
              <th>Project</th>
              <th>Strict</th>
              <th>Outcome</th>
              <th>Readiness</th>
              <th>Frameworks</th>
              <th>Findings</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {pageItems.map((scan) => {
              const findings = scan.findings?.length ?? 0;
              const tone = getToneFromStatus(scan.strict_result);
              return (
                <tr
                  key={scan.scan_id}
                  className={shared.tableRowLink}
                  onClick={() => router.push(`/pre-run/${scan.scan_id}`)}
                  style={{ cursor: "pointer" }}
                >
                  <td>
                    <Link href={`/pre-run/${scan.scan_id}`} className={shared.mono} onClick={(event) => event.stopPropagation()}>
                      {scan.scan_id}
                    </Link>
                  </td>
                  <td className={shared.tableMeta}>{scan.project_path}</td>
                  <td>
                    <Badge tone={scan.strict_mode ? "warning" : "neutral"}>
                      {scan.strict_mode ? "Strict" : "Advisory"}
                    </Badge>
                  </td>
                  <td>
                    <Badge tone={tone === "danger" ? "danger" : tone === "warning" ? "warning" : "success"}>
                      {scan.strict_result}
                    </Badge>
                  </td>
                  <td className={shared.tableMeta}>{Math.round(scan.readiness_score)}%</td>
                  <td className={shared.tableMeta}>{scan.frameworks?.join(", ") || "—"}</td>
                  <td className={shared.tableMeta}>{findings}</td>
                  <td className={shared.tableMeta}>{formatCompactDate(scan.created_at)}</td>
                </tr>
              );
            })}
            {pageItems.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  <div className={shared.emptyState}>
                    <div className={shared.emptyTitle}>No pre-run scans are available yet</div>
                    <div className={shared.emptyBody}>
                      Publish a CLI scan to populate this reviewer-facing history table.
                    </div>
                  </div>
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
        <div className={shared.tableFooter}>
          <span>{scans.length} total scans</span>
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
