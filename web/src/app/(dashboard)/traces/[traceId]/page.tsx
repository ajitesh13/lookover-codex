import { notFound } from "next/navigation";
import { TraceWorkspace } from "@/components/traces/trace-workspace";
import { getTraceDetail } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function TraceDetailPage({
  params,
}: {
  params: Promise<{ traceId: string }>;
}) {
  const { traceId } = await params;
  const detail = await getTraceDetail(traceId);

  if (!detail) {
    notFound();
  }

  return <TraceWorkspace detail={detail} />;
}
