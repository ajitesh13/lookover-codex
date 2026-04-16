import { BarChart3, CircleAlert, Sparkles } from "lucide-react";
import { ButtonLink } from "@/components/ui/button-link";
import { Badge } from "@/components/ui/badge";
import type { ApiTraceDetail, ApiTraceSummary } from "@/lib/lookover-api";
import {
  deriveTraceOutcome,
  formatRelativeTime,
  getToneFromStatus,
} from "@/lib/lookover-format";

type OverviewViewProps = {
  traces: ApiTraceSummary[];
  latestTraceId: string | null;
  latestScanId: string | null;
  latestDetail: ApiTraceDetail | null;
};

const scoreCards = [
  { key: "GDPR", className: "text-lookover-indigo" },
  { key: "EU_AI_ACT", className: "text-lookover-sky" },
  { key: "SOC2", className: "text-lookover-green" },
  { key: "OWASP_LLM_TOP_10_2025", className: "text-lookover-orange" },
  { key: "ISO_27001", className: "text-lookover-steel" },
];

function humanizeFramework(value: string) {
  return value
    .replaceAll("_", " ")
    .replace("EU AI ACT", "EU AI ACT")
    .replace("OWASP LLM TOP 10 2025", "OWASP")
    .replace("ISO 27001", "ISO 27001")
    .replace("SOC2", "SOC 2");
}

function getFrameworkScore(detail: ApiTraceDetail | null, framework: string) {
  if (!detail) return 0;
  const items = detail.findings.filter((item) => item.framework === framework);
  if (items.length === 0) return 0;

  const points = items.reduce((total, item) => {
    const status = item.status.toLowerCase();
    if (status.includes("cover")) return total + 1;
    if (status.includes("gap") || status.includes("partial")) return total + 0.45;
    return total + 0.12;
  }, 0);

  return Number(((points / items.length) * 100).toFixed(1));
}

function TrendChart({ values }: { values: number[] }) {
  const width = 960;
  const height = 220;
  const max = Math.max(...values, 100);
  const step = width / (values.length - 1);
  const points = values
    .map((value, index) => {
      const x = index * step;
      const y = height - (value / max) * (height - 20) - 10;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="relative h-[220px] w-full overflow-hidden rounded-[22px] border border-dashed border-slate-200 bg-slate-50/70 px-5 py-6">
      <div className="absolute inset-x-5 top-8 h-px border-t border-dashed border-slate-200" />
      <div className="absolute inset-x-5 top-[48%] h-px border-t border-dashed border-slate-200" />
      <div className="absolute inset-x-5 bottom-10 h-px border-t border-dashed border-slate-200" />
      <svg viewBox={`0 0 ${width} ${height}`} className="h-full w-full">
        <polyline
          fill="none"
          stroke="#111111"
          strokeWidth="3"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={points}
        />
        {values.map((value, index) => {
          const x = index * step;
          const y = height - (value / max) * (height - 20) - 10;
          return <circle key={`${value}-${index}`} cx={x} cy={y} r="5" fill="#111111" />;
        })}
      </svg>
    </div>
  );
}

export function OverviewView({
  traces,
  latestTraceId,
  latestScanId,
  latestDetail,
}: OverviewViewProps) {
  const latestTraces = traces.slice(0, 6);
  const openViolations = latestDetail
    ? latestDetail.findings.filter((item) => getToneFromStatus(item.status) === "danger").length
    : 0;
  const complianceScores = scoreCards.map((card) => ({
    label: humanizeFramework(card.key),
    value: getFrameworkScore(latestDetail, card.key),
    className: card.className,
  }));
  const highlightedBars = complianceScores.filter((item) => item.label === "GDPR" || item.label === "SOC 2");
  const trendValues = complianceScores.map((item) => item.value).concat(
    complianceScores.map((item, index) => Math.max(18, item.value - index * 8)),
  );

  return (
    <div className="space-y-9">
      <div className="grid gap-5 xl:grid-cols-5">
        {complianceScores.map((item) => (
          <section key={item.label} className="lookover-card px-8 py-7">
            <div className={`text-[14px] font-semibold uppercase tracking-[0.18em] ${item.className}`}>
              {item.label}
            </div>
            <div className="mt-6 flex items-end gap-1">
              <span className="text-[52px] font-semibold leading-none tracking-[-0.05em] text-slate-900">
                {item.value.toFixed(1)}
              </span>
              <span className="pb-1 text-[22px] font-medium text-slate-500">%</span>
            </div>
          </section>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.15fr,1fr]">
        <section className="lookover-card px-8 py-7">
          <div className="flex items-start justify-between">
            <div>
              <div className="lookover-label">Total traces (30d)</div>
              <div className="mt-6 text-[52px] font-semibold leading-none tracking-[-0.05em] text-slate-900">
                {traces.length}
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-50 text-slate-400">
              <Sparkles className="h-5 w-5" />
            </div>
          </div>
        </section>

        <section className="lookover-card px-8 py-7">
          <div className="flex items-start justify-between">
            <div>
              <div className="lookover-label">Open violations</div>
              <div className="mt-6 text-[52px] font-semibold leading-none tracking-[-0.05em] text-slate-900">
                {openViolations}
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-50 text-slate-400">
              <CircleAlert className="h-5 w-5" />
            </div>
          </div>
        </section>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.15fr,0.85fr]">
        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-8 py-6">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Recent Traces</h2>
          </div>
          <div className="space-y-4 px-8 py-8">
            {latestTraces.map((trace) => {
              const outcome = deriveTraceOutcome(trace);
              const tone =
                outcome === "Failure" ? "danger" : outcome === "In Progress" ? "warning" : "danger";
              return (
                <div
                  key={trace.trace_id}
                  className="grid grid-cols-[118px,1fr,auto,90px] items-center gap-4 text-[15px]"
                >
                  <span className="font-mono text-[15px] text-slate-500">{trace.trace_id.slice(0, 8)}</span>
                  <span className="truncate text-slate-900">{trace.agent_id || "agent"}</span>
                  <Badge tone={tone}>{outcome.toLowerCase()}</Badge>
                  <span className="text-right text-slate-500">{formatRelativeTime(trace.updated_at)}</span>
                </div>
              );
            })}
          </div>
        </section>

        <section className="lookover-card overflow-hidden">
          <div className="border-b border-lookover-border px-8 py-6">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">Compliance Scores</h2>
          </div>
          <div className="flex h-[430px] items-end justify-around gap-8 px-10 pb-8 pt-10">
            {highlightedBars.map((item) => (
              <div key={item.label} className="flex h-full w-full max-w-[160px] flex-col items-center justify-end gap-6">
                <div className="flex h-full w-full items-end justify-center">
                  <div
                    className="w-[72px] rounded-t-xl bg-[#3b3b3b]"
                    style={{ height: `${Math.max(40, item.value * 2.6)}px` }}
                  />
                </div>
                <div className="text-[16px] text-slate-400">{item.label}</div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="lookover-card overflow-hidden">
        <div className="border-b border-lookover-border px-8 py-6">
          <div className="flex items-center justify-between gap-4">
            <h2 className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">
              30-Day GDPR Compliance Trend
            </h2>
            <div className="flex flex-wrap items-center gap-3">
              <ButtonLink href={latestTraceId ? `/traces/${latestTraceId}` : "/traces"} tone="secondary">
                Open trace
              </ButtonLink>
              <ButtonLink href={latestScanId ? `/pre-run/${latestScanId}` : "/scans"} tone="primary">
                Open scan
              </ButtonLink>
            </div>
          </div>
        </div>
        <div className="px-8 py-8">
          <div className="mb-6 flex items-center gap-2 text-sm text-lookover-text-muted">
            <BarChart3 className="h-4 w-4" />
            <span>Trend line generated from current framework readiness signals.</span>
          </div>
          <TrendChart values={trendValues} />
        </div>
      </section>
    </div>
  );
}
