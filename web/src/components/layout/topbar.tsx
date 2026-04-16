"use client";

import { usePathname } from "next/navigation";
import styles from "./dashboard-shell.module.css";

const titleMap: Array<{ prefix: string; title: string }> = [
  { prefix: "/traces", title: "Traces" },
  { prefix: "/scans", title: "Scans" },
  { prefix: "/pre-run", title: "Pre-run" },
  { prefix: "/compliance", title: "Compliance" },
  { prefix: "/shared", title: "Shared Review" },
  { prefix: "/risk", title: "Risk" },
  { prefix: "/aibom", title: "AIBOM" },
  { prefix: "/violations", title: "Violations" },
  { prefix: "/audit-export", title: "Audit Export" },
  { prefix: "/gdpr", title: "GDPR" },
  { prefix: "/settings", title: "Settings" },
];

function resolveTitle(pathname: string) {
  if (pathname === "/") return "Overview";
  return titleMap.find((item) => pathname.startsWith(item.prefix))?.title ?? "Lookover Codex";
}

export function Topbar() {
  const pathname = usePathname();
  const title = resolveTitle(pathname);

  return (
    <header className={styles.topbar}>
      <div className={styles.topbarTitle}>{title}</div>
      <div className={styles.health}>
        <span className={styles.healthDot} />
        <span>System healthy</span>
      </div>
    </header>
  );
}
