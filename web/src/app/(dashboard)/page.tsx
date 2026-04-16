import { ButtonLink } from "@/components/ui/button-link";
import { MetricGrid } from "@/components/ui/metric-grid";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import shared from "@/components/ui/primitives.module.css";
import { getLatestPreRunScanId, getLatestTraceId, listPreRunScans, listTraces } from "@/lib/lookover-api";
import { formatCompactDate, getRiskLabel, titleCase } from "@/lib/lookover-format";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [traces, scans, latestTraceId, latestScanId] = await Promise.all([
    listTraces(),
    listPreRunScans(),
    getLatestTraceId(),
    getLatestPreRunScanId(),
  ]);

  const latestTrace = traces[0];
  const latestScan = scans[0];

  return (
    <div className={shared.section}>
      <PageHeader
        eyebrow="Overview"
        title="Reviewer control room"
        subtitle="A simple, white-mode audit dashboard for opening recent runs, inspecting live trace evidence, and checking pre-run readiness."
        actions={
          <>
            <ButtonLink href={latestTraceId ? `/traces/${latestTraceId}` : "/traces"} tone="primary">
              Open latest trace
            </ButtonLink>
            <ButtonLink href={latestScanId ? `/pre-run/${latestScanId}` : "/scans"}>Open latest scan</ButtonLink>
          </>
        }
      />

      <MetricGrid
        items={[
          {
            label: "Trace runs",
            value: String(traces.length),
            hint: latestTrace ? `Latest trace updated ${formatCompactDate(latestTrace.updated_at)}` : "No traces available yet.",
          },
          {
            label: "Pre-run scans",
            value: String(scans.length),
            hint: latestScan ? `Latest scan loaded from ${latestScan.project_path}` : "No scan history yet.",
          },
          {
            label: "Latest risk",
            value: latestTrace ? getRiskLabel(latestTrace.overall_risk_score) : "None",
            hint: latestTrace ? `Current reviewer run is ${latestTrace.status}.` : "A risk label appears after the first trace lands.",
          },
          {
            label: "Frameworks",
            value: latestScan?.frameworks.length ? String(latestScan.frameworks.length) : "0",
            hint: latestScan?.frameworks.length
              ? latestScan.frameworks.map((item) => titleCase(item)).join(", ")
              : "Framework mapping will show up after the first scan.",
          },
        ]}
      />

      <div className={shared.section} style={{ gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
        <SectionCard className={shared.stack}>
          <div className={shared.eyebrow}>Latest trace</div>
          <h2 className={shared.emptyTitle}>{latestTrace?.agent_id || "No trace loaded yet"}</h2>
          <p className={shared.emptyBody}>
            {latestTrace
              ? `Trace ${latestTrace.trace_id} is the most recent post-run record and can be opened directly into the audit workspace.`
              : "Once runtime evidence is ingested, the latest trace will appear here for one-click review."}
          </p>
          <ButtonLink href={latestTraceId ? `/traces/${latestTraceId}` : "/traces"}>
            {latestTraceId ? "Inspect trace" : "Open traces"}
          </ButtonLink>
        </SectionCard>

        <SectionCard className={shared.stack}>
          <div className={shared.eyebrow}>Latest pre-run</div>
          <h2 className={shared.emptyTitle}>{latestScan?.scan_id || "No scan loaded yet"}</h2>
          <p className={shared.emptyBody}>
            {latestScan
              ? `The latest readiness result for ${latestScan.project_path} is available with strict-mode outcome, findings, controls, evidence, and remediation.`
              : "When the CLI publishes a pre-run result, the newest scan will appear here."}
          </p>
          <ButtonLink href={latestScanId ? `/pre-run/${latestScanId}` : "/scans"}>
            {latestScanId ? "Inspect scan" : "Open scans"}
          </ButtonLink>
        </SectionCard>
      </div>
    </div>
  );
}
