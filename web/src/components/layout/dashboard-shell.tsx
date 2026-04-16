import styles from "./dashboard-shell.module.css";
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
    <div className={styles.shell}>
      <Sidebar reviewer={reviewer} />
      <div className={styles.body}>
        <Topbar />
        <main className={styles.content}>{children}</main>
      </div>
    </div>
  );
}
