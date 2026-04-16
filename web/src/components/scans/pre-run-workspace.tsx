import { ApiPreRunFinding, ApiPreRunScan } from "@/lib/lookover-api";
import {
  formatCompactDate,
  getSeverityTone,
  getToneFromStatus,
  safeText,
  titleCase,
} from "@/lib/lookover-format";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";

function formatSummaryLabel(key: string) {
  return titleCase(key.replaceAll("_", " "));
}

function flattenEvidence(findings: ApiPreRunFinding[]) {
  return findings.flatMap((finding) =>
    Object.entries(finding.evidence ?? {}).map(([key, value]) => ({
      id: `${finding.id}-${key}`,
      title: finding.title,
      ruleId: finding.rule_id,
      key,
      value: safeText(value),
    })),
  );
}

function CompactMetric({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-lookover-border bg-slate-50/75 px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
        {label}
      </div>
      <div className="mt-2 text-[24px] font-semibold leading-none tracking-[-0.04em] text-slate-900">
        {value}
      </div>
      <p className="mt-2 text-[12px] leading-5 text-lookover-text-muted">{hint}</p>
    </div>
  );
}

function EmptyListState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-lookover-border bg-slate-50/70 px-4 py-3 text-[13px] leading-6 text-lookover-text-muted">
      {message}
    </div>
  );
}

export function PreRunWorkspace({ scan }: { scan: ApiPreRunScan }) {
  const findings = scan.findings ?? [];
  const frameworks = scan.frameworks ?? [];
  const summaryEntries = Object.entries(scan.summary ?? {});
  const evidenceItems = flattenEvidence(findings);
  const metrics = [
    {
      label: "Readiness",
      value: `${Math.round(scan.readiness_score)}%`,
      hint: "Readiness score emitted by the CLI scan.",
    },
    {
      label: "Strict Mode",
      value: scan.strict_mode ? "On" : "Off",
      hint: "Strict mode promotes the most important gaps into a block result.",
    },
    {
      label: "Outcome",
      value: titleCase(scan.strict_result),
      hint: "Final pass, warn, or block result from the latest scan.",
    },
    {
      label: "Findings",
      value: String(findings.length),
      hint: "Total findings carried into this pre-run report.",
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        eyebrow="Pre-run"
        title={scan.project_path}
        subtitle="Builder-facing readiness view with strict-mode outcome, mapped controls, code and config evidence, and suggested remediation."
      />

      <SectionCard className="space-y-4 px-5 py-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1.5">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">{scan.scan_id}</h2>
            <p className="text-[13px] leading-6 text-lookover-text-muted">
              <span className="font-medium text-slate-900">Frameworks:</span>{" "}
              {frameworks.length > 0 ? frameworks.join(", ") : "none"}{" "}
              <span className="text-slate-300">·</span>{" "}
              <span className="font-medium text-slate-900">Created:</span> {formatCompactDate(scan.created_at)}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={scan.strict_mode ? "warning" : "neutral"}>
              {scan.strict_mode ? "Strict mode" : "Advisory mode"}
            </Badge>
            <Badge
              tone={
                getToneFromStatus(scan.strict_result) === "danger"
                  ? "danger"
                  : getToneFromStatus(scan.strict_result) === "warning"
                    ? "warning"
                    : "success"
              }
            >
              {scan.strict_result}
            </Badge>
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map((item) => (
            <CompactMetric key={item.label} label={item.label} value={item.value} hint={item.hint} />
          ))}
        </div>
      </SectionCard>

      <div className="grid items-start gap-4 xl:grid-cols-2">
        <SectionCard className="space-y-3 px-5 py-4">
          <h3 className="text-[14px] font-semibold tracking-[-0.02em] text-slate-900">Mapped controls</h3>
          <div className="space-y-2">
            {findings.length === 0 ? (
              <EmptyListState message="No mapped controls were returned for this scan." />
            ) : (
              findings.map((finding) => (
                <div
                  key={finding.id}
                  className="rounded-xl border border-lookover-border bg-slate-50/75 px-4 py-3"
                >
                  <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
                    {finding.rule_id}
                  </div>
                  <div className="mt-1.5 text-[13px] leading-6 text-slate-600">
                    {finding.control_refs.length > 0
                      ? finding.control_refs.join(", ")
                      : "No mapped controls"}
                  </div>
                </div>
              ))
            )}
          </div>
        </SectionCard>

        <SectionCard className="space-y-3 px-5 py-4">
          <h3 className="text-[14px] font-semibold tracking-[-0.02em] text-slate-900">Scan summary</h3>
          <div className="space-y-2">
            {summaryEntries.length === 0 ? (
              <EmptyListState message="No aggregate scan summary was returned for this result." />
            ) : (
              summaryEntries.map(([key, value]) => (
                <div
                  key={key}
                  className="flex items-start justify-between gap-4 rounded-xl border border-lookover-border bg-slate-50/75 px-4 py-3"
                >
                  <span className="text-[13px] font-semibold text-slate-900">
                    {formatSummaryLabel(key)}
                  </span>
                  <span className="max-w-[55%] text-right text-[13px] leading-6 text-slate-600">
                    {safeText(value)}
                  </span>
                </div>
              ))
            )}
          </div>
        </SectionCard>
      </div>

      <SectionCard className="space-y-3 px-5 py-4">
        <h3 className="text-[14px] font-semibold tracking-[-0.02em] text-slate-900">Findings</h3>
        <div className="space-y-2">
          {findings.length === 0 ? (
            <EmptyListState message="No findings were reported for this scan." />
          ) : (
            findings.map((finding) => (
              <div
                key={finding.id}
                className="rounded-xl border border-lookover-border bg-slate-50/75 px-4 py-3"
              >
                <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-1.5">
                    <div className="text-[14px] font-semibold tracking-[-0.02em] text-slate-900">
                      {finding.title}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={getSeverityTone(finding.severity)}>{finding.severity}</Badge>
                      <Badge
                        tone={
                          getToneFromStatus(finding.status) === "danger"
                            ? "danger"
                            : getToneFromStatus(finding.status) === "warning"
                              ? "warning"
                              : "success"
                        }
                      >
                        {finding.status}
                      </Badge>
                      <Badge tone="neutral">{finding.rule_id}</Badge>
                    </div>
                  </div>
                </div>
                <p className="mt-3 text-[13px] leading-6 text-lookover-text-muted">
                  {finding.remediation}
                </p>
              </div>
            ))
          )}
        </div>
      </SectionCard>

      <div className="grid items-start gap-4 xl:grid-cols-2">
        <SectionCard className="space-y-3 px-5 py-4">
          <h3 className="text-[14px] font-semibold tracking-[-0.02em] text-slate-900">Evidence</h3>
          <div className="space-y-2">
            {evidenceItems.length === 0 ? (
              <EmptyListState message="No evidence fields were attached to this scan." />
            ) : (
              evidenceItems.map((item) => (
                <div
                  key={item.id}
                  className="rounded-xl border border-lookover-border bg-slate-50/75 px-4 py-3"
                >
                  <div className="text-[12px] font-semibold text-slate-900">{item.title}</div>
                  <div className="mt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
                    {item.ruleId}
                  </div>
                  <div className="mt-2 text-[13px] leading-6 text-slate-600">
                    <strong className="font-semibold text-slate-900">{item.key}:</strong>{" "}
                    {item.value || "—"}
                  </div>
                </div>
              ))
            )}
          </div>
        </SectionCard>

        <SectionCard className="space-y-3 px-5 py-4">
          <h3 className="text-[14px] font-semibold tracking-[-0.02em] text-slate-900">Remediation</h3>
          <div className="space-y-2">
            {findings.length === 0 ? (
              <EmptyListState message="No remediation items were generated for this scan." />
            ) : (
              findings.map((finding) => (
                <div
                  key={`${finding.id}-remediation`}
                  className="rounded-xl border border-lookover-border bg-slate-50/75 px-4 py-3"
                >
                  <div className="flex items-start gap-3">
                    <span className="mt-2 h-1.5 w-1.5 flex-none rounded-full bg-slate-400" />
                    <div className="min-w-0 flex-1">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted">
                        {finding.rule_id}
                      </div>
                      <div className="mt-1.5 text-[13px] leading-6 text-slate-600">
                        {finding.remediation}
                      </div>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
