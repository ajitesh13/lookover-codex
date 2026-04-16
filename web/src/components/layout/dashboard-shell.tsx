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
      <div className="min-h-screen pl-[220px]">
        <Topbar />
        <main className="px-6 py-7 lg:px-12 lg:py-10">{children}</main>
      </div>
    </div>
  );
}
