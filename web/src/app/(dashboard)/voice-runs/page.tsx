import { VoiceRunsView } from "@/components/voice-runs/voice-runs-view";
import { getVoiceRunsReport } from "@/lib/lookover-api";

export const dynamic = "force-dynamic";

export default async function VoiceRunsPage() {
  const report = await getVoiceRunsReport();
  return <VoiceRunsView report={report} />;
}
