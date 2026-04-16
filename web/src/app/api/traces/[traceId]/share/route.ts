import { NextResponse } from "next/server";
import { getConfiguredApiBaseUrl } from "@/lib/lookover-config";
import type { ShareMode } from "@/lib/lookover-api";

type ShareResponse = {
  share_id: string;
  mode: ShareMode;
};

function normalizeMode(value: unknown): ShareMode {
  return value === "audit_log_only" ? "audit_log_only" : "audit_log_plus_evaluation";
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ traceId: string }> },
) {
  const { traceId } = await params;

  let payload: { mode?: ShareMode } = {};
  try {
    payload = (await request.json()) as { mode?: ShareMode };
  } catch {
    payload = {};
  }

  const mode = normalizeMode(payload.mode);
  const response = await fetch(new URL(`/v1/traces/${traceId}/share`, getConfiguredApiBaseUrl()).toString(), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ mode }),
    cache: "no-store",
  });

  if (!response.ok) {
    return NextResponse.json({ error: "Share link could not be created." }, { status: response.status });
  }

  const result = (await response.json()) as ShareResponse;
  const origin = new URL(request.url).origin;
  return NextResponse.json({
    ...result,
    url: `${origin}/shared/${result.share_id}`,
  });
}
