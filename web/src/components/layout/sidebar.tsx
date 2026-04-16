"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  AlertTriangle,
  Boxes,
  FileText,
  GitBranch,
  LayoutGrid,
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
};

const navItems: NavItem[] = [
  { href: "/overview", label: "Overview", icon: LayoutGrid },
  { href: "/traces", label: "Traces", icon: GitBranch },
  { href: "/compliance", label: "Compliance", icon: Shield },
  { href: "/risk", label: "Risk", icon: ShieldAlert },
  { href: "/aibom", label: "AIBOM", icon: Boxes },
  { href: "/violations", label: "Violations", icon: AlertTriangle },
  { href: "/audit-export", label: "Audit Export", icon: FileText },
  { href: "/gdpr", label: "GDPR", icon: UserRoundSearch },
  { href: "/settings", label: "Settings", icon: Settings },
];

function isActive(pathname: string, href: string) {
  if (href === "/") {
    return pathname === "/" || pathname === "/overview";
  }
  if (href === "/overview") {
    return pathname === "/" || pathname === "/overview";
  }
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
    <aside className="fixed inset-y-0 left-0 z-20 flex w-[220px] flex-col border-r border-lookover-border bg-lookover-sidebar shadow-lookover-rail">
      <div className="flex h-[110px] items-center border-b border-lookover-border px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-black text-white shadow-sm">
            <span className="text-sm font-semibold tracking-[-0.04em]">L</span>
          </div>
          <div>
            <div className="text-[19px] font-semibold tracking-[-0.04em] text-slate-900">Lookover</div>
            <div className="text-[12px] text-lookover-text-muted">Codex</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-4 py-10">
        {navItems.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex h-12 items-center gap-3 rounded-2xl px-5 text-[15px] font-medium text-slate-500 transition",
                active
                  ? "bg-black text-white shadow-sm"
                  : "hover:bg-white hover:text-slate-900",
              )}
            >
              <Icon className="h-[18px] w-[18px]" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-lookover-border px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-slate-300 bg-[#262626] text-base font-medium text-white shadow-sm">
            {getInitials(reviewer.email)}
          </div>
          <div className="min-w-0">
            <div className="truncate text-[14px] font-medium text-slate-900">{reviewer.email}</div>
            <div className="text-[12px] text-lookover-text-muted">{reviewer.role === "reviewer" ? "Owner" : reviewer.role}</div>
          </div>
        </div>
        <button
          type="button"
          className="mt-4 text-[14px] font-medium text-lookover-text-muted transition hover:text-slate-900"
          onClick={handleLogout}
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
