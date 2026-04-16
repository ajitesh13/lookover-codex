import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { TraceWorkspace } from "@/components/traces/trace-workspace";
import { EmptyState } from "@/components/ui/empty-state";
import { getSharedTrace } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function SharedPage({
  params,
}: {
  params: Promise<{ shareId: string }>;
}) {
  const { shareId } = await params;
  const cookieStore = await cookies();

  if (!cookieStore.get("lookover_session_token")?.value?.trim()) {
    redirect(`/login?next=${encodeURIComponent(`/shared/${shareId}`)}`);
  }

  const shared = await getSharedTrace(shareId);
  if (!shared) {
    return (
      <EmptyState
        title="The shared run could not be loaded"
        body="The link may be invalid, expired, or the backend may not currently be reachable."
      />
    );
  }

  return <TraceWorkspace detail={shared.trace} readOnly shareMode={shared.mode} />;
}
