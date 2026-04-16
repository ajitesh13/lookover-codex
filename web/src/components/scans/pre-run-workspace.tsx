import { ApiPreRunScan } from "@/lib/lookover-api";
import {
  formatCompactDate,
  getSeverityTone,
  getToneFromStatus,
  safeText,
} from "@/lib/lookover-format";
import { Badge } from "@/components/ui/badge";
import { MetricGrid } from "@/components/ui/metric-grid";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import shared from "@/components/ui/primitives.module.css";
import styles from "./scans.module.css";

export function PreRunWorkspace({ scan }: { scan: ApiPreRunScan }) {
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
      value: scan.strict_result,
      hint: "Final pass, warn, or block result from the latest scan.",
    },
    {
      label: "Findings",
      value: String(scan.findings.length),
      hint: "Total findings carried into this pre-run report.",
    },
  ];

  return (
    <div className={shared.section}>
      <PageHeader
        eyebrow="Pre-run"
        title={scan.project_path}
        subtitle="Builder-facing readiness view with strict-mode outcome, mapped controls, code and config evidence, and suggested remediation."
      />

      <SectionCard className={styles.detailCard}>
        <div className={styles.detailTop}>
          <div className={styles.detailTitle}>
            <h2>{scan.scan_id}</h2>
            <p>
              Frameworks: {scan.frameworks.join(", ") || "none"} · Created {formatCompactDate(scan.created_at)}
            </p>
          </div>
          <div className={styles.detailMeta}>
            <Badge tone={scan.strict_mode ? "warning" : "neutral"}>
              {scan.strict_mode ? "Strict mode" : "Advisory mode"}
            </Badge>
            <Badge tone={getToneFromStatus(scan.strict_result) === "danger" ? "danger" : getToneFromStatus(scan.strict_result) === "warning" ? "warning" : "success"}>
              {scan.strict_result}
            </Badge>
          </div>
        </div>
        <MetricGrid items={metrics} />
      </SectionCard>

      <div className={styles.twoColumn}>
        <SectionCard className={styles.detailCard}>
          <div className={shared.stack}>
            <div className={styles.findingTitle}>Mapped controls</div>
            <div className={styles.evidenceList}>
              {scan.findings.map((finding) => (
                <div key={finding.id} className={styles.evidenceItem}>
                  <div className={styles.evidenceLabel}>{finding.rule_id}</div>
                  <div className={styles.evidenceValue}>{finding.control_refs.join(", ") || "No mapped controls"}</div>
                </div>
              ))}
            </div>
          </div>
        </SectionCard>

        <SectionCard className={styles.detailCard}>
          <div className={shared.stack}>
            <div className={styles.findingTitle}>Scan summary</div>
            <div className={styles.evidenceList}>
              {Object.entries(scan.summary ?? {}).map(([key, value]) => (
                <div key={key} className={styles.evidenceItem}>
                  <div className={styles.evidenceLabel}>{key}</div>
                  <div className={styles.evidenceValue}>{safeText(value)}</div>
                </div>
              ))}
            </div>
          </div>
        </SectionCard>
      </div>

      <SectionCard className={styles.detailCard}>
        <div className={styles.findingTitle}>Findings</div>
        <div className={styles.findingList}>
          {scan.findings.map((finding) => (
            <div key={finding.id} className={`${shared.cardInset} ${styles.findingCard}`}>
              <div className={styles.findingTitle}>{finding.title}</div>
              <div className={styles.findingMeta}>
                <Badge tone={getSeverityTone(finding.severity)}>{finding.severity}</Badge>
                <Badge tone={getToneFromStatus(finding.status) === "danger" ? "danger" : getToneFromStatus(finding.status) === "warning" ? "warning" : "success"}>
                  {finding.status}
                </Badge>
                <Badge tone="neutral">{finding.rule_id}</Badge>
              </div>
              <div className={styles.findingBody}>{finding.remediation}</div>
            </div>
          ))}
        </div>
      </SectionCard>

      <div className={styles.twoColumn}>
        <SectionCard className={styles.detailCard}>
          <div className={styles.findingTitle}>Evidence</div>
          <div className={styles.evidenceList}>
            {scan.findings.flatMap((finding) =>
              Object.entries(finding.evidence ?? {}).map(([key, value]) => (
                <div key={`${finding.id}-${key}`} className={styles.evidenceItem}>
                  <div className={styles.evidenceLabel}>{finding.title}</div>
                  <div className={styles.evidenceValue}>
                    <strong>{key}:</strong> {safeText(value)}
                  </div>
                </div>
              )),
            )}
          </div>
        </SectionCard>

        <SectionCard className={styles.detailCard}>
          <div className={styles.findingTitle}>Remediation</div>
          <div className={styles.evidenceList}>
            {scan.findings.map((finding) => (
              <div key={`${finding.id}-remediation`} className={styles.evidenceItem}>
                <div className={styles.evidenceLabel}>{finding.rule_id}</div>
                <div className={styles.evidenceValue}>{finding.remediation}</div>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
