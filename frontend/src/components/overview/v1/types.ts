/**
 * V1 rep overview types — 5 independent per-section agents, each with own citations.
 */

import type { Citation } from "@/types";

export interface ResearchSummary {
  policy_positions: string[] | null;
  policy_positions_citations: Citation[];
  recent_legislative_record: string[] | null;
  recent_legislative_record_citations: Citation[];
  accomplishments: string[] | null;
  accomplishments_citations: Citation[];
  controversies: string[] | null;
  controversies_citations: Citation[];
  top_donors: string[] | null;
  top_donors_citations: Citation[];
}
