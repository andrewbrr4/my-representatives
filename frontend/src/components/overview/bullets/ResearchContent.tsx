/**
 * Bullets research content renderer — single blended bullet list with
 * inline citation markers resolved against a unified citation pool.
 *
 * While loading with no bullets yet, shows a per-node progress bar plus a
 * rotating fun-facts carousel. Once bullets start streaming in, renders them
 * with a small trailer skeleton until the task completes.
 */

import type { BulletsResearchSummary } from "./types";
import type { ProgressInfo } from "@/types";
import { FurtherReading } from "@/components/FurtherReading";
import { renderInline } from "@/components/overview/renderInline";
import { ResearchProgress } from "@/components/overview/ResearchProgress";
import { FactsCarousel } from "@/components/overview/FactsCarousel";
import { Skeleton } from "@/components/ui/skeleton";

function BulletsTrailerSkeleton() {
  return (
    <div className="space-y-1 pt-1" aria-hidden>
      <Skeleton className="h-3.5 w-5/6" />
      <Skeleton className="h-3.5 w-2/3" />
    </div>
  );
}

export function ResearchContent({
  summary,
  status,
  progress,
}: {
  summary: BulletsResearchSummary;
  status?: "loading" | "complete" | "failed";
  progress?: ProgressInfo | null;
}) {
  const { bullets, citations, sources } = summary;

  // Nothing written yet: show the progress bar + facts carousel.
  if (bullets.length === 0) {
    return (
      <div className="space-y-2 text-sm leading-relaxed">
        <FactsCarousel />
        <ResearchProgress progress={progress} />
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
      {status === "loading" && <BulletsTrailerSkeleton />}
      <FurtherReading sources={sources} />
    </div>
  );
}
