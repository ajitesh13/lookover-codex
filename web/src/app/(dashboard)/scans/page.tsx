import { ScanListView } from "@/components/scans/scan-list-view";
import { listPreRunScans } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function ScansPage() {
  const scans = await listPreRunScans();
  return <ScanListView scans={scans} />;
}
