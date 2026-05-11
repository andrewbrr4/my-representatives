/**
 * Bullets research content renderer — single blended bullet list with
 * inline citation markers resolved against a unified citation pool.
 *
 * Used by any overview pipeline version that produces a BulletsResearchSummary
 * (currently v2, v3, v4). When v4 emits ``sources`` (gated on the
 * ``OVERVIEW_V4_SHOW_SOURCES`` backend flag), an expandable "Further reading (N)"
 * list renders below the bullets — a jumping-off point for the user's own
 * research, distinct from the inline citation markers (which exist to back
 * up the bullets themselves).
 */

import type { BulletsResearchSummary } from "./types";
import { FurtherReading } from "@/components/FurtherReading";
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
  const { bullets, citations, sources } = summary;

  // Empty bullets = task hasn't written synthesis yet; parent's loading message
  // ("Scraping the web...") is the primary indicator — skeleton is the filler below it.
  if (bullets.length === 0) {
    return (
      <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
        <BulletsSkeleton />
      </div>
    );
  }

  return (
    <div className="space-y-3 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none mt-2">
      <ul className="list-disc pl-5 space-y-1.5 marker:text-muted-foreground">
        {bullets.map((b, i) => (
          <li key={i}>{renderInline(b, citations)}</li>
        ))}
      </ul>
      <FurtherReading sources={sources} />
    </div>
  );
}
