import { cn } from "@/lib/utils.js";

export function Card({ className, ...props }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card text-card-foreground shadow-[0_1px_0_0_rgba(255,255,255,0.03)_inset,0_8px_24px_-12px_rgba(0,0,0,0.6)]",
        className,
      )}
      {...props}
    />
  );
}
