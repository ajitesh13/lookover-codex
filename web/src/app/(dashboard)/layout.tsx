import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getReviewerFromCookie } from "@/lib/lookover-api";

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const reviewer =
    getReviewerFromCookie(cookieStore.get("lookover_session_user")?.value) ?? {
      email: "reviewer@lookover.local",
      role: "reviewer",
    };

  return <DashboardShell reviewer={reviewer}>{children}</DashboardShell>;
}
