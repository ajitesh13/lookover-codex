import { NextResponse } from "next/server";
import { getConfiguredApiBaseUrl } from "@/lib/lookover-config";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const target = new URL("/v1/voice-runs", getConfiguredApiBaseUrl());
  target.search = url.search;

  const response = await fetch(target.toString(), {
    cache: "no-store",
    headers: {
      Accept: "application/json",
    },
  });

  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

export async function POST(request: Request) {
  const body = await request.text();
  const response = await fetch(new URL("/v1/voice-runs", getConfiguredApiBaseUrl()).toString(), {
    method: "POST",
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body,
  });

  const responseBody = await response.text();
  return new NextResponse(responseBody, {
    status: response.status,
    headers: {
      "Content-Type": "application/json",
    },
  });
}
