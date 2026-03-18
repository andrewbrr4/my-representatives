import type { Representative, Citation } from "@/types";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

function renderInline(
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
  content: string;
  citations: Citation[];
}

function ParagraphSection({ title, content, citations }: ParagraphSectionProps) {
  return (
    <div>
      <h4 className="font-semibold text-foreground">{title}</h4>
      <p>{renderInline(content, citations)}</p>
    </div>
  );
}

interface ListSectionProps {
  title: string;
  items: string[];
  citations: Citation[];
}

function ListSection({ title, items, citations }: ListSectionProps) {
  return (
    <div>
      <h4 className="font-semibold text-foreground">{title}</h4>
      <ul className="list-disc pl-5 space-y-1">
        {items.map((item, i) => (
          <li key={i}>{renderInline(item, citations)}</li>
        ))}
      </ul>
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
}

export function RepCard({ rep }: RepCardProps) {
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
        {rep.summary === undefined ? (
          <div className="space-y-2">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        ) : rep.summary ? (
          <div className="space-y-2 text-sm leading-relaxed prose prose-sm prose-neutral dark:prose-invert max-w-none">
            <ParagraphSection title="Background" content={rep.summary.background} citations={rep.summary.background_citations ?? []} />
            <ParagraphSection title="Policy Positions" content={rep.summary.policy_positions} citations={rep.summary.policy_positions_citations ?? []} />
            <ListSection title="Recent Legislative Record" items={rep.summary.recent_legislative_record} citations={rep.summary.recent_legislative_record_citations ?? []} />
            <ListSection title="Accomplishments" items={rep.summary.accomplishments} citations={rep.summary.accomplishments_citations ?? []} />
            <ListSection title="Controversies" items={rep.summary.controversies} citations={rep.summary.controversies_citations ?? []} />
            <ListSection title="Other Recent Press" items={rep.summary.recent_press} citations={rep.summary.recent_press_citations ?? []} />
            <ListSection title="Top Donors" items={rep.summary.top_donors} citations={rep.summary.top_donors_citations ?? []} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground italic">
            Research unavailable for this representative.
          </p>
        )}

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
      </CardContent>
    </Card>
  );
}
