export type DemoReviewerSession = {
  token: string;
  user: {
    id: string;
    email: string;
    role: "reviewer";
  };
  demo: true;
};

export function normalizeDemoReviewerEmail(email?: string) {
  const normalized = String(email ?? "").trim();
  return normalized || "reviewer@lookover.local";
}

export function createDemoReviewerSession(email?: string): DemoReviewerSession {
  const normalizedEmail = normalizeDemoReviewerEmail(email);

  return {
    token: `demo-session:${encodeURIComponent(normalizedEmail)}`,
    user: {
      id: "demo-reviewer",
      email: normalizedEmail,
      role: "reviewer",
    },
    demo: true,
  };
}

export function getDemoReviewerAuthHint() {
  return "Any email/password combination is accepted in demo mode.";
}
