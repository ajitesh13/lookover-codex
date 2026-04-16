import { cn } from "@/lib/lookover-format";
import styles from "./primitives.module.css";

type BadgeTone = "neutral" | "success" | "warning" | "danger";

export function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
}) {
  return (
    <span
      className={cn(
        styles.badge,
        tone === "success" && styles.badgeSuccess,
        tone === "warning" && styles.badgeWarning,
        tone === "danger" && styles.badgeDanger,
        tone === "neutral" && styles.badgeNeutral,
      )}
    >
      {children}
    </span>
  );
}
