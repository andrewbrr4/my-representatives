import type { ProgressInfo } from "@/types";

/**
 * Filling progress bar shown while a rep overview is being researched.
 * Driven by per-node progress from the backend; falls back to 0% /
 * "Getting started" on the first poll before any node has reported.
 */
export function ResearchProgress({ progress }: { progress?: ProgressInfo | null }) {
  const pct = progress?.pct ?? 0;
  const label = progress?.label ?? "Getting started";
  const clamped = Math.min(100, Math.max(0, pct));

  return (
    <div className="space-y-1.5 mt-1">
      <div className="flex items-center justify-between text-xs font-medium text-muted-foreground">
        <span className="italic">{label}…</span>
        <span>{clamped}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-foreground transition-all duration-700 ease-out"
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
