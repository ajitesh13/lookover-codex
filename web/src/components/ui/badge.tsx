import { cn } from "@/lib/lookover-format";

type BadgeTone = "neutral" | "success" | "warning" | "danger";

const toneClasses: Record<BadgeTone, string> = {
  neutral: "border-slate-200 bg-slate-50 text-slate-500",
  success: "border-emerald-200 bg-emerald-50 text-emerald-600",
  warning: "border-amber-200 bg-amber-50 text-amber-600",
  danger: "border-rose-200 bg-rose-50 text-rose-500",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-[12px] font-medium leading-none",
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
