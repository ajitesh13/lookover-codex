import Link from "next/link";
import { cn } from "@/lib/lookover-format";
import styles from "./primitives.module.css";

type ButtonTone = "primary" | "secondary" | "ghost";

export function ButtonLink({
  href,
  children,
  tone = "secondary",
}: {
  href: string;
  children: React.ReactNode;
  tone?: ButtonTone;
}) {
  return (
    <Link
      href={href}
      className={cn(
        styles.button,
        tone === "primary" && styles.buttonPrimary,
        tone === "secondary" && styles.buttonSecondary,
        tone === "ghost" && styles.buttonGhost,
      )}
    >
      {children}
    </Link>
  );
}
