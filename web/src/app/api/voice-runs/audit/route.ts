import { NextResponse } from "next/server";
import { getConfiguredApiBaseUrl } from "@/lib/lookover-config";

export async function POST(request: Request) {
  let payload: { transcript?: string } = {};
  try {
    payload = (await request.json()) as { transcript?: string };
  } catch {
    payload = {};
  }

  const transcript = String(payload.transcript ?? "").trim();
  if (!transcript) {
    return NextResponse.json({ error: "Transcript is required." }, { status: 400 });
  }

  const response = await fetch(new URL("/v1/voice-runs", getConfiguredApiBaseUrl()).toString(), {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ transcript }),
    cache: "no-store",
  });

  const responseBody = await response.text();
  if (!response.ok) {
    try {
      const parsed = JSON.parse(responseBody) as { detail?: string; error?: string };
      return NextResponse.json({ error: parsed.error || parsed.detail || "Voice audit failed." }, { status: response.status });
    } catch {
      return NextResponse.json({ error: "Voice audit failed." }, { status: response.status });
    }
  }

  return new NextResponse(responseBody, {
    status: response.status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}
