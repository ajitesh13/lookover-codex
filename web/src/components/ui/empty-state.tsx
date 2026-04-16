export function EmptyState({
  title,
  body,
}: {
  title: string;
  body: string;
}) {
  return (
    <div className="lookover-card flex min-h-[240px] flex-col items-center justify-center px-8 py-10 text-center">
      <h2 className="text-xl font-semibold tracking-[-0.03em] text-slate-900">{title}</h2>
      <p className="mt-3 max-w-xl text-[15px] leading-7 text-lookover-text-muted">{body}</p>
    </div>
  );
}
