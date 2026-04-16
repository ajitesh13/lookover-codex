"use client";

import { usePathname } from "next/navigation";

const titleMap: Array<{ prefix: string; title: string }> = [
  { prefix: "/overview", title: "Overview" },
  { prefix: "/traces", title: "Trace Detail" },
  { prefix: "/scans", title: "Scans" },
  { prefix: "/pre-run", title: "Pre-run" },
  { prefix: "/compliance", title: "Compliance" },
  { prefix: "/shared", title: "Shared Review" },
  { prefix: "/voice-runs", title: "Voice Runs" },
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
  if (pathname === "/voice-runs") return "Voice Runs";
  return titleMap.find((item) => pathname.startsWith(item.prefix))?.title ?? "Lookover Codex";
}

export function Topbar() {
  const pathname = usePathname();
  const title = resolveTitle(pathname);

  return (
    <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-lookover-border/90 bg-white/75 px-5 backdrop-blur-md lg:px-10">
      <div className="text-[17px] font-semibold tracking-[-0.03em] text-slate-900">{title}</div>
      <div className="inline-flex items-center gap-2.5 text-[13px] font-medium text-slate-500">
        <span className="h-3.5 w-3.5 rounded-full bg-emerald-400/15 p-[3px]">
          <span className="block h-full w-full rounded-full bg-emerald-500" />
        </span>
        <span>System healthy</span>
      </div>
    </header>
  );
}
