/**
 * V1 research content renderer — 5 sections with per-section citations,
 * revealed top-down as each agent completes.
 */

import type { Citation } from "@/types";
import type { ResearchSummary } from "./types";
import { renderInline } from "@/components/overview/renderInline";
import { Skeleton } from "@/components/ui/skeleton";

function SectionSkeleton() {
  return (
    <div className="space-y-1.5 mt-1">
      <Skeleton className="h-3.5 w-full" />
      <Skeleton className="h-3.5 w-5/6" />
    </div>
  );
}

interface ParagraphSectionProps {
  title: string;
  content: string | null;
  citations: Citation[];
}

function ParagraphSection({ title, content, citations }: ParagraphSectionProps) {
  return (
    <div>
      <h4 className="font-semibold text-foreground">{title}</h4>
      {content === null ? (
        <SectionSkeleton />
      ) : (
        <p>{renderInline(content, citations)}</p>
      )}
    </div>
  );
}

interface ListSectionProps {
  title: string;
  items: string[] | null;
  citations: Citation[];
}

function ListSection({ title, items, citations }: ListSectionProps) {
  return (
    <div>
      <h4 className="font-semibold text-foreground">{title}</h4>
      {items === null ? (
        <SectionSkeleton />
      ) : (
        <ul className="list-disc pl-5 space-y-1">
          {items.map((item, i) => (
            <li key={i}>{renderInline(item, citations)}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// Sections in display order — content is only revealed once all preceding sections are complete.
const SECTION_ORDER: {
  key: keyof ResearchSummary;
  citationsKey: keyof ResearchSummary;
  title: string;
  kind: "paragraph" | "list";
}[] = [
  { key: "policy_positions", citationsKey: "policy_positions_citations", title: "Policy Positions", kind: "list" },
  { key: "recent_legislative_record", citationsKey: "recent_legislative_record_citations", title: "Recent Legislative Record", kind: "list" },
  { key: "accomplishments", citationsKey: "accomplishments_citations", title: "Accomplishments", kind: "list" },
  { key: "controversies", citationsKey: "controversies_citations", title: "Controversies", kind: "list" },
  { key: "top_donors", citationsKey: "top_donors_citations", title: "Top Donors", kind: "list" },
];

export function ResearchContent({ summary }: { summary: ResearchSummary }) {
  // Find the first section that hasn't completed yet — everything after it stays skeleton
  let allPriorComplete = true;

  return (
    <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
      {SECTION_ORDER.map((section) => {
        const content = summary[section.key];
        const citations = (summary[section.citationsKey] as Citation[]) ?? [];
        // Only reveal this section's content if all prior sections are complete
        const showContent = allPriorComplete && content !== null;
        if (content === null) allPriorComplete = false;

        if (section.kind === "paragraph") {
          return (
            <ParagraphSection
              key={section.key}
              title={section.title}
              content={showContent ? (content as unknown as string) : null}
              citations={citations}
            />
          );
        }
        return (
          <ListSection
            key={section.key}
            title={section.title}
            items={showContent ? (content as string[]) : null}
            citations={citations}
          />
        );
      })}
    </div>
  );
}
