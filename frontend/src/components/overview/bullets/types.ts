/**
 * Shared rep overview schema for v2+ — a single blended bullet list
 * with a unified citation pool.
 *
 * ``sources`` is populated by v4 when ``OVERVIEW_V4_SHOW_SOURCES`` is on:
 * the deduped breadth+depth Tavily pool that informed the bullets,
 * rendered as a "Further reading" expandable list below the bullets.
 */

import type { Citation } from "@/types";
import type { SourceLink } from "@/components/FurtherReading";

export type { SourceLink };

export interface BulletsResearchSummary {
  bullets: string[];
  citations: Citation[];
  sources?: SourceLink[];
}
