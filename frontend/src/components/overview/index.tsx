/**
 * Overview dispatch: the backend may return a v1 sectioned summary OR a
 * BulletsResearchSummary (v2, v3). Consumers get a single ResearchContent
 * component and a union type; the component picks a renderer at runtime
 * based on the response shape.
 */

import type { ResearchSummary as V1ResearchSummary } from "./v1";
import type { BulletsResearchSummary } from "./bullets";
import { ResearchContent as V1ResearchContent } from "./v1";
import { ResearchContent as BulletsResearchContent } from "./bullets";

export type ResearchSummary = V1ResearchSummary | BulletsResearchSummary;

export function isBullets(summary: ResearchSummary): summary is BulletsResearchSummary {
  return "bullets" in summary;
}

export function ResearchContent({ summary }: { summary: ResearchSummary }) {
  if (isBullets(summary)) {
    return <BulletsResearchContent summary={summary} />;
  }
  return <V1ResearchContent summary={summary} />;
}
