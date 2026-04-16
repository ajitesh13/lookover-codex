"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  Boxes,
  FileText,
  GitBranch,
  LayoutGrid,
  Mic,
  ScanSearch,
  Settings,
  Shield,
  ShieldAlert,
  UserRoundSearch,
} from "lucide-react";
import { cn } from "@/lib/lookover-format";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  enabled: boolean;
  activePrefixes?: string[];
};

const navItems: NavItem[] = [
  { href: "/overview", label: "Overview", icon: LayoutGrid, enabled: true },
  { href: "/traces", label: "Traces", icon: GitBranch, enabled: true, activePrefixes: ["/traces", "/shared"] },
  { href: "/voice-runs", label: "Voice Runs", icon: Mic, enabled: true },
  { href: "/scans", label: "Pre Run", icon: ScanSearch, enabled: true, activePrefixes: ["/scans", "/pre-run"] },
  { href: "/compliance", label: "Compliance", icon: Shield, enabled: false },
  { href: "/risk", label: "Risk", icon: ShieldAlert, enabled: false },
  { href: "/aibom", label: "AIBOM", icon: Boxes, enabled: false },
  { href: "/violations", label: "Violations", icon: AlertTriangle, enabled: false },
  { href: "/audit-export", label: "Audit Export", icon: FileText, enabled: false },
  { href: "/gdpr", label: "GDPR", icon: UserRoundSearch, enabled: false },
  { href: "/settings", label: "Settings", icon: Settings, enabled: false },
];

function isActive(pathname: string, item: NavItem) {
  const prefixes = item.activePrefixes ?? [item.href];
  if (item.href === "/") {
    return pathname === "/" || pathname === "/overview";
  }
  if (item.href === "/overview") {
    return pathname === "/" || pathname === "/overview";
  }
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
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
    <aside className="fixed inset-y-0 left-0 z-20 flex w-[214px] flex-col border-r border-lookover-border/90 bg-white/90 backdrop-blur-md shadow-lookover-rail">
      <div className="flex h-[88px] items-center border-b border-lookover-border/90 px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl border border-black/10 bg-black text-white shadow-sm">
            <span className="text-sm font-semibold tracking-[-0.04em]">L</span>
          </div>
          <div>
            <div className="text-[17px] font-semibold tracking-[-0.04em] text-slate-900">Lookover</div>
            <div className="text-[12px] text-lookover-text-muted">Codex</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1.5 overflow-y-auto px-3 py-7">
        {navItems.map((item) => {
          const active = isActive(pathname, item);
          const Icon = item.icon;
          const itemClassName = cn(
            "flex h-11 items-center gap-3 rounded-xl px-4 text-[14px] font-medium transition",
            active && item.enabled
              ? "bg-[#0f1115] text-white shadow-sm"
              : item.enabled
                ? "text-slate-500 hover:bg-black/[0.03] hover:text-slate-900"
                : "cursor-not-allowed text-slate-300",
          );

          if (!item.enabled) {
            return (
              <div key={item.href} className={itemClassName} aria-disabled="true" title={`${item.label} is not active yet`}>
                <Icon className="h-[17px] w-[17px]" />
                <span>{item.label}</span>
              </div>
            );
          }

          return (
            <Link key={item.href} href={item.href} className={itemClassName}>
              <Icon className="h-[17px] w-[17px]" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-lookover-border/90 px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full border border-slate-300 bg-[#262626] text-sm font-medium text-white shadow-sm">
            {getInitials(reviewer.email)}
          </div>
          <div className="min-w-0">
            <div className="truncate text-[13px] font-medium text-slate-900">{reviewer.email}</div>
            <div className="text-[12px] text-lookover-text-muted">{reviewer.role === "reviewer" ? "Owner" : reviewer.role}</div>
          </div>
        </div>
        <button
          type="button"
          className="mt-3 text-[13px] font-medium text-lookover-text-muted transition hover:text-slate-900"
          onClick={handleLogout}
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
