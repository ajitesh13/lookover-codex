import { cn } from "@/lib/lookover-format";

export function SectionCard({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return <section className={cn("lookover-card", className)}>{children}</section>;
}
