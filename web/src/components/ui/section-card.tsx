import styles from "./primitives.module.css";

export function SectionCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={`${styles.card} ${className ?? ""}`.trim()}>{children}</section>;
}
