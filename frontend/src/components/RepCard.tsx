import { ChevronDown, ChevronRight } from "lucide-react";
import type { Representative, ResearchSummary, Citation } from "@/types";
import type { ResearchStatus } from "@/hooks/useResearchQuery";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function renderInline(
  text: string,
  citations: Citation[],
): React.ReactNode {
  // Match **bold**, *italic*, and [N] citations
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|\[\d+\])/g);
  return parts.map((part, i) => {
    // Bold: **text**
    const boldMatch = part.match(/^\*\*(.+)\*\*$/);
    if (boldMatch) {
      return <strong key={i}>{boldMatch[1]}</strong>;
    }
    // Italic: *text*
    const italicMatch = part.match(/^\*(.+)\*$/);
    if (italicMatch) {
      return <em key={i}>{italicMatch[1]}</em>;
    }
    // Citation: [N]
    const citeMatch = part.match(/^\[(\d+)\]$/);
    if (citeMatch) {
      const idx = parseInt(citeMatch[1], 10) - 1;
      const citation = citations[idx];
      if (citation) {
        return (
          <sup key={i}>
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              title={citation.title}
              className="text-primary hover:text-primary/80 ml-0.5"
            >
              [{citeMatch[1]}]
            </a>
          </sup>
        );
      }
    }
    return part;
  });
}

interface ParagraphSectionProps {
  title: string;
  content: string | null;
  citations: Citation[];
}

function SectionSkeleton() {
  return (
    <div className="space-y-1.5 mt-1">
      <Skeleton className="h-3.5 w-full" />
      <Skeleton className="h-3.5 w-5/6" />
    </div>
  );
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
  { key: "background", citationsKey: "background_citations", title: "Background", kind: "paragraph" },
  { key: "policy_positions", citationsKey: "policy_positions_citations", title: "Policy Positions", kind: "paragraph" },
  { key: "recent_legislative_record", citationsKey: "recent_legislative_record_citations", title: "Recent Legislative Record", kind: "list" },
  { key: "accomplishments", citationsKey: "accomplishments_citations", title: "Accomplishments", kind: "list" },
  { key: "controversies", citationsKey: "controversies_citations", title: "Controversies", kind: "list" },
  { key: "recent_press", citationsKey: "recent_press_citations", title: "Other Recent Press", kind: "list" },
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
              content={showContent ? (content as string) : null}
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

const levelColors: Record<string, string> = {
  federal: "bg-blue-600 text-white hover:bg-blue-700",
  state: "bg-amber-600 text-white hover:bg-amber-700",
  municipal: "bg-emerald-600 text-white hover:bg-emerald-700",
};

interface RepCardProps {
  rep: Representative;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  onResearch: () => void;
}

export function RepCard({ rep, researchStatus, summary, onResearch }: RepCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start gap-4 space-y-0">
        {rep.photo_url ? (
          <img
            src={rep.photo_url}
            alt={rep.name}
            className="w-16 h-16 rounded-full object-cover border-2 border-muted flex-shrink-0"
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center text-muted-foreground text-xl font-semibold flex-shrink-0">
            {rep.name.charAt(0)}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-lg">{rep.name}</CardTitle>
            <Badge className={levelColors[rep.level] || ""}>
              {rep.level}
            </Badge>
          </div>
          <CardDescription className="mt-1">
            {rep.office}
            {rep.party && ` · ${rep.party}`}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Contact links */}
        <div className="flex gap-3 text-sm flex-wrap">
          {rep.contact.website && (
            <a
              href={rep.contact.website}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline underline-offset-2 hover:text-primary/80"
            >
              Website
            </a>
          )}
          {rep.contact.phone && (
            <a
              href={`tel:${rep.contact.phone}`}
              className="text-primary underline underline-offset-2 hover:text-primary/80"
            >
              {rep.contact.phone}
            </a>
          )}
          {rep.contact.email && (
            <a
              href={`mailto:${rep.contact.email}`}
              className="text-primary underline underline-offset-2 hover:text-primary/80"
            >
              Email
            </a>
          )}
        </div>

        {/* Research states */}
        {researchStatus === "idle" && (
          <Button onClick={onResearch} variant="outline" className="w-full">
            Generate AI Research
          </Button>
        )}

        {researchStatus === "loading" && !summary && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground italic">
              Scraping the web for information about your representative -- this usually takes 30-60 seconds...
            </p>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {(researchStatus === "loading" && summary) && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Research
              <span className="ml-1 text-xs text-muted-foreground italic">(Scraping the web for information about your representative -- this usually takes 30-60 seconds...)</span>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "complete" && summary && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Research
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "failed" && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground italic">
              Research unavailable for this representative.
            </p>
            <Button onClick={onResearch} variant="outline" size="sm">
              Retry
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
