import { NextResponse } from "next/server";
import { createDemoReviewerSession } from "../../_lib/auth";

export async function POST(request: Request) {
  let body: { email?: string; password?: string } = {};
  try {
    body = (await request.json()) as { email?: string; password?: string };
  } catch {
    body = {};
  }

  const email = String(body.email ?? "").trim();
  const password = String(body.password ?? "").trim();
  // Dummy auth is intentional for the current demo flow.
  void password;
  const session = createDemoReviewerSession(email);

  const response = NextResponse.json(session);

  response.cookies.set("lookover_session_token", session.token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24,
  });
  response.cookies.set("lookover_session_user", JSON.stringify(session.user), {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    secure: process.env.NODE_ENV === "production",
    maxAge: 60 * 60 * 24,
  });
  return response;
}
