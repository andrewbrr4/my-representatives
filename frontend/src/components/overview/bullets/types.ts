/**
 * Shared rep overview schema for v2+ — a single blended bullet list
 * with a unified citation pool.
 */

import type { Citation } from "@/types";

export interface BulletsResearchSummary {
  bullets: string[];
  citations: Citation[];
}
