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
import { getPartyBadge } from "@/lib/partyBadge";

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
          <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">
            {rep.office}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-2xl font-bold tracking-tight">{rep.name}</CardTitle>
            {(() => {
              const badge = getPartyBadge(rep.party);
              return badge ? <Badge className={badge.className}>{badge.label}</Badge> : null;
            })()}
          </div>
          {rep.party && (
            <CardDescription className="mt-1 text-sm">{rep.party}</CardDescription>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Contact links */}
        {(rep.contact.website || rep.contact.phone || rep.contact.email) && (
          <div className="space-y-1">
            <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Contact
            </p>
            <div className="flex gap-4 text-sm flex-wrap">
              {rep.contact.website && (
                <a
                  href={rep.contact.website}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-primary underline underline-offset-2 hover:text-primary/80"
                >
                  Website
                </a>
              )}
              {rep.contact.phone && (
                <a
                  href={`tel:${rep.contact.phone}`}
                  className="font-medium text-primary underline underline-offset-2 hover:text-primary/80"
                >
                  {rep.contact.phone}
                </a>
              )}
              {rep.contact.email && (
                <a
                  href={`mailto:${rep.contact.email}`}
                  className="font-medium text-primary underline underline-offset-2 hover:text-primary/80"
                >
                  Email
                </a>
              )}
            </div>
          </div>
        )}

        {/* Research states — kept above IssueSearch in every state so the
            issue search never jumps up when the AI button is clicked. */}
        {researchStatus === "idle" && (
          <div className="space-y-1.5">
            <Button onClick={onResearch} variant="secondary" className="w-full font-semibold uppercase tracking-wide">
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
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Overview
              <span className="ml-2 text-[11px] font-medium normal-case tracking-normal text-muted-foreground italic">(scraping the web — usually 30-60 seconds…)</span>
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
              <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer group">
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

        {/* OR divider — only when both options are equally salient (idle) */}
        {researchStatus === "idle" && (
          <div className="flex items-center gap-3 text-xs uppercase tracking-wide text-muted-foreground">
            <div className="flex-1 border-t" />
            <span>or</span>
            <div className="flex-1 border-t" />
          </div>
        )}

        {/* Issue search — always at the bottom so it doesn't shift on click */}
        <IssueSearch rep={rep} />
      </CardContent>
    </Card>
  );
}
