import { OverviewView } from "@/components/overview/overview-view";
import {
  getLatestPreRunScanId,
  getLatestTraceId,
  getTraceDetail,
  listTraces,
} from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function OverviewPage() {
  const [traces, latestTraceId, latestScanId] = await Promise.all([
    listTraces(),
    getLatestTraceId(),
    getLatestPreRunScanId(),
  ]);

  const detailCandidates = await Promise.all(traces.slice(0, 20).map((trace) => getTraceDetail(trace.trace_id)));
  const latestDetail = detailCandidates[0] ?? (latestTraceId ? await getTraceDetail(latestTraceId) : null);
  const scoreDetail = detailCandidates.find((detail) => (detail?.findings.length ?? 0) > 0) ?? latestDetail;

  return (
    <OverviewView
      traces={traces}
      latestTraceId={latestTraceId}
      latestScanId={latestScanId}
      latestDetail={latestDetail}
      scoreDetail={scoreDetail}
    />
  );
}
