import { notFound } from "next/navigation";
import { PreRunWorkspace } from "@/components/scans/pre-run-workspace";
import { getPreRunScan } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function PreRunDetailPage({
  params,
}: {
  params: Promise<{ scanId: string }>;
}) {
  const { scanId } = await params;
  const scan = await getPreRunScan(scanId);

  if (!scan) {
    notFound();
  }

  return <PreRunWorkspace scan={scan} />;
}
