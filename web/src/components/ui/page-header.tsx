import { cn } from "@/lib/lookover-format";

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
  className,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between", className)}>
      <div className="space-y-2">
        {eyebrow ? <div className="lookover-label">{eyebrow}</div> : null}
        <h1 className="text-[20px] font-semibold tracking-[-0.03em] text-slate-900">{title}</h1>
        {subtitle ? <p className="max-w-3xl text-[14px] leading-6 text-lookover-text-muted">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-3">{actions}</div> : null}
    </div>
  );
}
