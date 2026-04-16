import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ArrowLeft, ShieldCheck } from "lucide-react";
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

  return (
    <div className="min-h-screen bg-lookover-bg">
      <header className="sticky top-0 z-10 border-b border-lookover-border/90 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-[1280px] items-center justify-between px-5 lg:px-8">
          <Link
            href="/overview"
            className="inline-flex items-center gap-3 text-slate-900 transition hover:text-black"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-black/10 bg-black text-sm font-semibold text-white">
              L
            </div>
            <div className="space-y-0.5">
              <div className="text-[14px] font-semibold tracking-[-0.02em]">Lookover</div>
              <div className="text-[12px] text-lookover-text-muted">Shared review</div>
            </div>
          </Link>
          <div className="inline-flex items-center gap-2 rounded-xl border border-lookover-border bg-white px-3 py-2 text-[13px] font-medium text-slate-600">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            <span>Read-only session</span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1280px] px-5 py-6 lg:px-8 lg:py-8">
        <div className="mb-4">
          <Link
            href="/overview"
            className="inline-flex items-center gap-2 text-[13px] font-medium text-lookover-text-muted transition hover:text-slate-900"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Back to workspace</span>
          </Link>
        </div>

        {!shared ? (
          <EmptyState
            title="The shared run could not be loaded"
            body="The link may be invalid, expired, or the backend may not currently be reachable."
          />
        ) : (
          <TraceWorkspace detail={shared.trace} readOnly shareMode={shared.mode} />
        )}
      </main>
    </div>
  );
}
