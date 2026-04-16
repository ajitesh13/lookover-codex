import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

export function DashboardShell({
  reviewer,
  children,
}: {
  reviewer: { email: string; role: string };
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-lookover-bg">
      <Sidebar reviewer={reviewer} />
      <div className="min-h-screen pl-[214px]">
        <Topbar />
        <main className="px-5 py-6 lg:px-10 lg:py-8">{children}</main>
      </div>
    </div>
  );
}
