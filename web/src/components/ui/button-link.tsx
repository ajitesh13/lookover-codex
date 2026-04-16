import Link from "next/link";
import { cn } from "@/lib/lookover-format";

type ButtonTone = "primary" | "secondary" | "ghost";

const toneClasses: Record<ButtonTone, string> = {
  primary: "bg-[#111113] text-white shadow-sm hover:bg-[#1b1b20]",
  secondary: "border border-lookover-border bg-white text-lookover-text hover:bg-white",
  ghost: "bg-transparent text-lookover-text-muted hover:bg-black/[0.03] hover:text-lookover-text",
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
        "inline-flex h-10 items-center justify-center rounded-xl px-4 text-[13px] font-semibold transition",
        toneClasses[tone],
        className,
      )}
    >
      {children}
    </Link>
  );
}
