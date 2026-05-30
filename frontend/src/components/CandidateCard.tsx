import type { Candidate, Representative, ResearchSummary, ProgressInfo } from "@/types";
import type { ResearchStatus } from "@/hooks/useResearchQuery";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { ResearchContent } from "@/components/overview";
import { IssueSearch } from "@/components/IssueSearch";
import { getPartyBadge } from "@/lib/partyBadge";

interface CandidateCardProps {
  candidate: Candidate;
  rep: Representative;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  progress?: ProgressInfo | null;
  onResearch: () => void;
}

export function CandidateCard({
  candidate,
  rep,
  researchStatus,
  summary,
  progress,
  onResearch,
}: CandidateCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-start gap-4 space-y-0">
        {candidate.photo_url ? (
          <img
            src={candidate.photo_url}
            alt={candidate.name}
            className="w-16 h-16 rounded-full object-cover border-2 border-muted flex-shrink-0"
          />
        ) : (
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center text-muted-foreground text-xl font-semibold flex-shrink-0">
            {candidate.name.charAt(0)}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground mb-1">
            {candidate.office}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-2xl font-bold tracking-tight">{candidate.name}</CardTitle>
            {(() => {
              const badge = getPartyBadge(candidate.party);
              return badge ? <Badge className={badge.className}>{badge.label}</Badge> : null;
            })()}
            {candidate.incumbent && (
              <Badge variant="outline" className="text-[10px] font-bold uppercase tracking-wider">Incumbent</Badge>
            )}
          </div>
          {candidate.party && (
            <CardDescription className="mt-1 text-sm">{candidate.party}</CardDescription>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Issue search */}
        <IssueSearch rep={rep} />

        {/* Research states */}
        {researchStatus === "idle" && (
          <Button onClick={onResearch} variant="outline" className="w-full font-semibold uppercase tracking-wide">
            Generate AI Overview
          </Button>
        )}

        {researchStatus === "loading" && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Overview
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent
                summary={summary ?? { bullets: [], citations: [] }}
                status="loading"
                progress={progress}
              />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "complete" && summary && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-bold uppercase tracking-wider text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Overview
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} status="complete" />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "failed" && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground italic">
              Research unavailable for this candidate.
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
