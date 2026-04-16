import { redirect } from "next/navigation";
import { EmptyState } from "@/components/ui/empty-state";
import { getLatestPreRunScanId } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function PreRunPage() {
  const latestScanId = await getLatestPreRunScanId();
  if (latestScanId) {
    redirect(`/pre-run/${latestScanId}`);
  }
  return (
    <EmptyState
      title="No pre-run scan is available yet"
      body="Publish a pre-run CLI result first, then this compatibility route will forward straight into the newest scan detail page."
    />
  );
}
