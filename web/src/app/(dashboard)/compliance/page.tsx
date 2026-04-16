import { redirect } from "next/navigation";
import { EmptyState } from "@/components/ui/empty-state";
import { getLatestTraceId } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function CompliancePage() {
  const latestTraceId = await getLatestTraceId();
  if (latestTraceId) {
    redirect(`/traces/${latestTraceId}`);
  }
  return (
    <EmptyState
      title="No trace is available for compliance review"
      body="Ingest a runtime trace first, then this compatibility route will forward straight into the latest trace workspace."
    />
  );
}
