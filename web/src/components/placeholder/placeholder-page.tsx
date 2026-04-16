import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";
import styles from "@/components/ui/primitives.module.css";

export function PlaceholderPage({
  eyebrow,
  title,
  subtitle,
  detail,
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  detail: string;
}) {
  return (
    <div className={styles.section}>
      <PageHeader eyebrow={eyebrow} title={title} subtitle={subtitle} />
      <SectionCard className={styles.stack}>
        <EmptyState title={`${title} is staged for the next pass`} body={detail} />
      </SectionCard>
    </div>
  );
}
