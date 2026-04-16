"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, CheckCircle2, Shield, Sparkles } from "lucide-react";
import { getDemoReviewerAuthHint } from "../_lib/auth";

type AuthMode = "login" | "signup";

type AuthShellProps = {
  mode: AuthMode;
  nextPath?: string;
};

function authCopy(mode: AuthMode) {
  if (mode === "signup") {
    return {
      eyebrow: "Create access",
      title: "Create a reviewer session",
      lead: "Any email and password creates the same dummy reviewer session used across all agent runs.",
      primaryLabel: "Create session",
      secondaryHref: "/login",
      secondaryLabel: "Back to login",
      footer: "Already have a session?",
    };
  }

  return {
    eyebrow: "Reviewer access",
    title: "Sign in to inspect runs",
    lead: "Any email and password opens the same local reviewer session and unlocks all shared and internal runs.",
    primaryLabel: "Sign in",
    secondaryHref: "/signup",
    secondaryLabel: "Create a session",
    footer: "Need a reviewer session?",
  };
}

function resolveNextLabel(nextPath: string) {
  if (nextPath.startsWith("/shared/")) return "shared review";
  if (nextPath.startsWith("/traces")) return "trace review";
  if (nextPath.startsWith("/pre-run") || nextPath.startsWith("/scans")) return "pre-run scan";
  return "workspace";
}

export function AuthShell({ mode, nextPath = "/overview" }: AuthShellProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const copy = authCopy(mode);
  const nextLabel = resolveNextLabel(nextPath);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const response = await fetch(mode === "login" ? "/api/login" : "/api/signup", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      if (response.ok) {
        window.location.assign(nextPath);
        return;
      }

      const payload = (await response.json().catch(() => null)) as { error?: string } | null;
      setError(payload?.error || "The demo session could not be started.");
    } catch {
      setError("The demo session could not be started.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-lookover-bg">
      <div className="mx-auto flex min-h-screen max-w-[1180px] items-center px-5 py-8 lg:px-10">
        <div className="grid w-full overflow-hidden rounded-[20px] border border-lookover-border bg-white shadow-lookover-card lg:grid-cols-[1.05fr,0.95fr]">
          <section className="flex flex-col justify-between gap-8 bg-[#0f1115] px-7 py-8 text-white lg:px-8 lg:py-10">
            <div className="space-y-8">
              <div className="inline-flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/5 text-sm font-semibold">
                  LC
                </div>
                <div className="space-y-0.5">
                  <div className="text-[15px] font-semibold tracking-[-0.02em]">Lookover Codex</div>
                  <div className="text-[12px] text-white/55">Audit workspace</div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-white/45">
                  {copy.eyebrow}
                </div>
                <h1 className="max-w-[12ch] text-[34px] font-semibold leading-[1.02] tracking-[-0.05em]">
                  {copy.title}
                </h1>
                <p className="max-w-xl text-[14px] leading-7 text-white/70">{copy.lead}</p>
              </div>

              <div className="rounded-[16px] border border-white/10 bg-white/[0.04] p-4">
                <div className="flex items-center gap-2 text-[13px] font-medium text-white">
                  <Shield className="h-4 w-4 text-white/70" />
                  <span>Session destination</span>
                </div>
                <p className="mt-2 text-[13px] leading-6 text-white/65">
                  After authentication, you&apos;ll go straight into the {nextLabel}.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-start gap-3 rounded-[14px] border border-white/10 bg-white/[0.04] px-4 py-3">
                <CheckCircle2 className="mt-0.5 h-4 w-4 flex-none text-emerald-400" />
                <div className="text-[13px] leading-6 text-white/68">
                  Shared links, traces, and pre-run scans all use the same local reviewer session.
                </div>
              </div>
              <div className="flex items-start gap-3 rounded-[14px] border border-white/10 bg-white/[0.04] px-4 py-3">
                <Sparkles className="mt-0.5 h-4 w-4 flex-none text-sky-400" />
                <div className="text-[13px] leading-6 text-white/68">
                  Demo auth stays intentionally frictionless so you can move directly into review.
                </div>
              </div>
            </div>
          </section>

          <section className="px-6 py-7 lg:px-8 lg:py-10">
            <div className="mx-auto max-w-[380px] space-y-6">
              <div className="space-y-2">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-lookover-text-muted">
                  Reviewer session
                </div>
                <div className="text-[24px] font-semibold tracking-[-0.04em] text-slate-900">
                  {mode === "login" ? "Welcome back" : "Set up access"}
                </div>
                <p className="text-[13px] leading-6 text-lookover-text-muted">
                  Use any email and password to continue.
                </p>
              </div>

              {error ? (
                <div className="rounded-[14px] border border-rose-200 bg-rose-50 px-4 py-3 text-[13px] leading-6 text-rose-600">
                  {error}
                </div>
              ) : null}

              <form className="space-y-4" onSubmit={submit}>
                <div className="space-y-1.5">
                  <label
                    htmlFor="email"
                    className="text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted"
                  >
                    Email
                  </label>
                  <input
                    id="email"
                    name="email"
                    type="email"
                    className="lookover-input w-full"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="reviewer@company.com"
                  />
                </div>

                <div className="space-y-1.5">
                  <label
                    htmlFor="password"
                    className="text-[11px] font-semibold uppercase tracking-[0.14em] text-lookover-text-muted"
                  >
                    Password
                  </label>
                  <input
                    id="password"
                    name="password"
                    type="password"
                    className="lookover-input w-full"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Any password works"
                  />
                </div>

                <div className="space-y-3 pt-1">
                  <button
                    className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-[#111113] px-4 text-[13px] font-semibold text-white shadow-sm transition hover:bg-[#1b1b20] disabled:opacity-60"
                    type="submit"
                    disabled={isSubmitting}
                  >
                    <span>{isSubmitting ? "Opening session..." : copy.primaryLabel}</span>
                    {!isSubmitting ? <ArrowRight className="h-4 w-4" /> : null}
                  </button>
                  <Link
                    href={copy.secondaryHref}
                    className="inline-flex h-10 w-full items-center justify-center rounded-xl border border-lookover-border bg-white text-[13px] font-semibold text-slate-900 transition hover:bg-slate-50"
                  >
                    {copy.secondaryLabel}
                  </Link>
                </div>
              </form>

              <div className="rounded-[14px] border border-lookover-border bg-slate-50/80 px-4 py-3 text-[13px] leading-6 text-lookover-text-muted">
                {getDemoReviewerAuthHint()}
              </div>

              <div className="text-[13px] leading-6 text-lookover-text-muted">
                {copy.footer}{" "}
                <Link href={copy.secondaryHref} className="font-semibold text-slate-900 transition hover:text-black">
                  {copy.secondaryLabel}
                </Link>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
