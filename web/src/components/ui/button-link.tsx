import Link from "next/link";
import { cn } from "@/lib/lookover-format";

type ButtonTone = "primary" | "secondary" | "ghost";

const toneClasses: Record<ButtonTone, string> = {
  primary: "bg-black text-white hover:bg-slate-900",
  secondary: "border border-lookover-border bg-white text-lookover-text hover:bg-slate-50",
  ghost: "bg-transparent text-lookover-text-muted hover:bg-slate-100 hover:text-lookover-text",
};

export function ButtonLink({
  href,
  children,
  tone = "secondary",
  className,
}: {
  href: string;
  children: React.ReactNode;
  tone?: ButtonTone;
  className?: string;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex h-11 items-center justify-center rounded-2xl px-4 text-sm font-medium transition",
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </Link>
  );
}
