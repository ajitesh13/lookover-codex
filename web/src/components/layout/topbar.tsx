"use client";

import { usePathname } from "next/navigation";

const titleMap: Array<{ prefix: string; title: string }> = [
  { prefix: "/overview", title: "Overview" },
  { prefix: "/traces", title: "Trace Detail" },
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
  if (pathname === "/traces") return "Traces";
  if (pathname.startsWith("/traces/")) return "Trace Detail";
  return titleMap.find((item) => pathname.startsWith(item.prefix))?.title ?? "Lookover Codex";
}

export function Topbar() {
  const pathname = usePathname();
  const title = resolveTitle(pathname);

  return (
    <header className="sticky top-0 z-10 flex h-[72px] items-center justify-between border-b border-lookover-border bg-white/90 px-12 backdrop-blur">
      <div className="text-[18px] font-semibold tracking-[-0.03em] text-slate-900">{title}</div>
      <div className="inline-flex items-center gap-3 text-[14px] font-medium text-slate-500">
        <span className="h-4 w-4 rounded-full bg-emerald-400/20 p-[3px]">
          <span className="block h-full w-full rounded-full bg-emerald-400" />
        </span>
        <span>System healthy</span>
      </div>
    </header>
  );
}
