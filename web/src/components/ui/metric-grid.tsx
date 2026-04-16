import styles from "./primitives.module.css";

export type MetricItem = {
  label: string;
  value: string;
  hint: string;
};

export function MetricGrid({ items }: { items: MetricItem[] }) {
  return (
    <div className={styles.metrics}>
      {items.map((item) => (
        <div key={item.label} className={`${styles.card} ${styles.metricCard}`}>
          <div className={styles.metricLabel}>{item.label}</div>
          <div className={styles.metricValue}>{item.value}</div>
          <div className={styles.metricHint}>{item.hint}</div>
        </div>
      ))}
    </div>
  );
}
