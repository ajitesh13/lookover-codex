import styles from "./primitives.module.css";

export function EmptyState({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className={`${styles.card} ${styles.emptyState}`}>
      <h2 className={styles.emptyTitle}>{title}</h2>
      <p className={styles.emptyBody}>{body}</p>
    </div>
  );
}
