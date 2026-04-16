"use client";

import Link from "next/link";
import { useState } from "react";
import { getDemoReviewerAuthHint } from "../_lib/auth";
import styles from "./auth-shell.module.css";

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

export function AuthShell({ mode, nextPath = "/compliance" }: AuthShellProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const copy = authCopy(mode);

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
    <div className={styles.page}>
      <div className={styles.card}>
        <div className={styles.brand}>
          <div className={styles.brandRow}>
            <span className={styles.brandMark}>LC</span>
            <span className={styles.brandMeta}>
              <span className={styles.brandTitle}>Lookover Codex</span>
              <span className={styles.brandCopy}>Audit workspace</span>
            </span>
          </div>

          <div className={styles.title}>
            <div className={styles.eyebrow}>{copy.eyebrow}</div>
            <h1>{copy.title}</h1>
            <p className={styles.lead}>{copy.lead}</p>
          </div>
        </div>

        {error ? <div className={styles.error}>{error}</div> : null}

        <form className={styles.form} onSubmit={submit}>
          <div className={styles.field}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="reviewer@company.com"
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Any password works"
            />
          </div>

          <div className={styles.actions}>
            <button className={styles.primaryButton} type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Opening session..." : copy.primaryLabel}
            </button>
            <Link href={copy.secondaryHref} className={styles.secondaryButton}>
              {copy.secondaryLabel}
            </Link>
          </div>
        </form>

        <div className={styles.note}>{getDemoReviewerAuthHint()}</div>
        <div className={styles.footer}>
          {copy.footer} <Link href={copy.secondaryHref}>{copy.secondaryLabel}</Link>
        </div>
      </div>
    </div>
  );
}
