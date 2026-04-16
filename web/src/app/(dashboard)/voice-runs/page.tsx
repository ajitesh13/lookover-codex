import { VoiceRunsView } from "@/components/voice-runs/voice-runs-view";
import { listVoiceRuns } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function VoiceRunsPage() {
  const response = await listVoiceRuns();
  return <VoiceRunsView initialResponse={response} />;
}
