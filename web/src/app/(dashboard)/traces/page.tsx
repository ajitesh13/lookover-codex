import { TraceListView } from "@/components/traces/trace-list-view";
import { listTraces } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function TracesPage() {
  const traces = await listTraces();
  return <TraceListView traces={traces} />;
}
