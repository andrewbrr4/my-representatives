import { ChevronDown, ChevronRight, Sparkles } from "lucide-react";
import type { Representative, ResearchSummary } from "@/types";
import type { ResearchStatus } from "@/hooks/useResearchQuery";
import { IssueSearch } from "@/components/IssueSearch";
import { ResearchContent, isBullets } from "@/components/overview";
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

function getPartyBadge(party: string | null): { label: string; className: string } | null {
  if (!party) return null;
  const p = party.trim().toLowerCase();
  if (p === "d" || p.startsWith("democrat")) {
    // Match the input form so the badge doesn't say "Democrat" while the
    // CardDescription says "· Democratic" on the same card.
    const label = p.startsWith("democratic") ? "Democratic" : "Democrat";
    return { label, className: "bg-blue-600 text-white hover:bg-blue-700" };
  }
  if (p === "r" || p.startsWith("republican")) {
    return { label: "Republican", className: "bg-red-600 text-white hover:bg-red-700" };
  }
  if (p === "i" || p.startsWith("independent")) {
    return { label: "Independent", className: "bg-slate-500 text-white hover:bg-slate-600" };
  }
  return null;
}

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
            {(() => {
              const badge = getPartyBadge(rep.party);
              return badge ? <Badge className={badge.className}>{badge.label}</Badge> : null;
            })()}
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

        {/* Issue search */}
        <IssueSearch rep={rep} />

        {/* Research states */}
        {researchStatus === "idle" && (
          <div className="space-y-1">
            <Button onClick={onResearch} className="w-full">
              <Sparkles className="h-4 w-4" />
              Generate AI Overview
            </Button>
            <p className="text-xs text-muted-foreground text-center">
              See their record, accomplishments, and controversies — researched live in ~30 seconds.
            </p>
          </div>
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
              AI Overview
              <span className="ml-1 text-xs text-muted-foreground italic">(Scraping the web for information about your representative -- this usually takes 30-60 seconds...)</span>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "complete" && summary && (
          // Defensive: a bullets-shaped summary with zero bullets means the
          // formatter retry exhausted but the backend still marked the task
          // complete. Treat as failure so the user gets an actionable retry
          // instead of a stuck-forever skeleton.
          isBullets(summary) && summary.bullets.length === 0 ? (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground italic">
                Research unavailable for this representative.
              </p>
              <Button onClick={onResearch} variant="outline" size="sm">
                Retry
              </Button>
            </div>
          ) : (
            <Collapsible defaultOpen>
              <CollapsibleTrigger className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
                <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
                <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
                AI Overview
              </CollapsibleTrigger>
              <CollapsibleContent>
                <ResearchContent summary={summary} />
              </CollapsibleContent>
            </Collapsible>
          )
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
