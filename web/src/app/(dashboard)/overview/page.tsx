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

  const latestDetail = latestTraceId ? await getTraceDetail(latestTraceId) : null;

  return (
    <OverviewView
      traces={traces}
      latestTraceId={latestTraceId}
      latestScanId={latestScanId}
      latestDetail={latestDetail}
    />
  );
}
