/**
 * Bullets research content renderer — single blended bullet list with
 * inline citation markers resolved against a unified citation pool.
 *
 * Used by any overview pipeline version that produces a BulletsResearchSummary
 * (currently v2 and v3).
 */

import type { BulletsResearchSummary } from "./types";
import { renderInline } from "@/components/overview/renderInline";
import { Skeleton } from "@/components/ui/skeleton";

function BulletsSkeleton() {
  return (
    <div className="space-y-2 mt-1">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="space-y-1">
          <Skeleton className="h-3.5 w-5/6" />
          <Skeleton className="h-3.5 w-3/4" />
        </div>
      ))}
    </div>
  );
}

export function ResearchContent({ summary }: { summary: BulletsResearchSummary }) {
  const { bullets, citations } = summary;

  if (bullets === null) {
    return (
      <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
        <BulletsSkeleton />
      </div>
    );
  }

  return (
    <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
      <ul className="list-disc pl-5 space-y-1">
        {bullets.map((b, i) => (
          <li key={i}>{renderInline(b, citations)}</li>
        ))}
      </ul>
    </div>
  );
}
