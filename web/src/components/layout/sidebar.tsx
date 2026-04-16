"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { cn } from "@/lib/lookover-format";
import styles from "./dashboard-shell.module.css";

type NavItem = {
  href: string;
  label: string;
  icon: string;
};

const navItems: NavItem[] = [
  { href: "/", label: "Overview", icon: "OV" },
  { href: "/traces", label: "Traces", icon: "TR" },
  { href: "/scans", label: "Scans", icon: "SC" },
  { href: "/compliance", label: "Compliance", icon: "CO" },
  { href: "/risk", label: "Risk", icon: "RI" },
  { href: "/aibom", label: "AIBOM", icon: "AI" },
  { href: "/violations", label: "Violations", icon: "VI" },
  { href: "/audit-export", label: "Audit Export", icon: "AE" },
  { href: "/gdpr", label: "GDPR", icon: "GD" },
  { href: "/settings", label: "Settings", icon: "ST" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (pathname.startsWith("/shared")) {
    return href === "/traces";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function getInitials(email: string) {
  const [local] = email.split("@");
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function Sidebar({
  reviewer,
}: {
  reviewer: { email: string; role: string };
}) {
  const pathname = usePathname();
  const router = useRouter();

  async function handleLogout() {
    await fetch("/api/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <aside className={styles.sidebar}>
      <div className={styles.brand}>
        <span className={styles.brandMark}>LC</span>
        <div className={styles.brandText}>
          <span className={styles.brandTitle}>Lookover Codex</span>
          <span className={styles.brandCopy}>Audit workspace</span>
        </div>
      </div>

      <nav className={styles.nav}>
        <div className={styles.navSection}>
          {navItems.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(styles.navLink, active && styles.navLinkActive)}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </nav>

      <div className={styles.footer}>
        <div className={styles.reviewer}>
          <span className={styles.avatar}>{getInitials(reviewer.email)}</span>
          <div className={styles.reviewerCopy}>
            <span className={styles.reviewerEmail}>{reviewer.email}</span>
            <span className={styles.reviewerRole}>{reviewer.role}</span>
          </div>
        </div>
        <button type="button" className={styles.logout} onClick={handleLogout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
