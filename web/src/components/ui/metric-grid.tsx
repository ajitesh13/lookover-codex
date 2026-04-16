export type MetricItem = {
  label: string;
  value: string;
  hint: string;
  accentClassName?: string;
};

export function MetricGrid({ items }: { items: MetricItem[] }) {
  return (
    <div className="grid gap-5 xl:grid-cols-5">
      {items.map((item) => (
        <div key={item.label} className="lookover-card flex min-h-[146px] flex-col justify-between px-8 py-7">
          <div className={`text-[14px] font-semibold uppercase tracking-[0.16em] ${item.accentClassName ?? "text-lookover-text-muted"}`}>
            {item.label}
          </div>
          <div className="flex items-end gap-2">
            <span className="text-[54px] font-semibold leading-none tracking-[-0.05em] text-slate-900">
              {item.value}
            </span>
          </div>
          <p className="text-[14px] leading-6 text-lookover-text-muted">{item.hint}</p>
        </div>
      ))}
    </div>
  );
}
