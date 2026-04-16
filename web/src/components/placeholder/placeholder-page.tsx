import { PageHeader } from "@/components/ui/page-header";
import { SectionCard } from "@/components/ui/section-card";

export function PlaceholderPage({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <div className="space-y-8">
      <PageHeader eyebrow={eyebrow} title={title} subtitle={body} />
      <SectionCard className="px-8 py-8">
        <div className="lookover-label">Coming soon</div>
        <h2 className="mt-3 text-[28px] font-semibold tracking-[-0.04em] text-slate-900">{title}</h2>
        <p className="mt-4 max-w-2xl text-[15px] leading-7 text-lookover-text-muted">
          This module is intentionally present in the navigation so the dashboard mirrors the Lookover information architecture, even while the page body is still being expanded.
        </p>
      </SectionCard>
    </div>
  );
}
