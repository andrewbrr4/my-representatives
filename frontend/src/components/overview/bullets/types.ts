/**
 * Shared rep overview schema for the bullet-list UX (the default pipeline
 * and legacy v2/v3) — a single blended bullet list with a unified citation
 * pool and inline [N] markers.
 *
 * ``sources`` is populated by the default pipeline when ``OVERVIEW_V4_SHOW_SOURCES``
 * is on: a deduped breadth+depth pool projected to {title, url} entries, rendered
 * as an expandable "Further reading (N)" list below the bullets.
 */

import type { Citation } from "@/types";
import type { SourceLink } from "@/components/FurtherReading";

export type { SourceLink };

export interface BulletsResearchSummary {
  bullets: string[];
  citations: Citation[];
  sources?: SourceLink[];
}
