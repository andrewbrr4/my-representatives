import type { Candidate, ResearchSummary } from "@/types";
import type { ResearchStatus } from "@/hooks/useResearchQuery";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { ResearchContent } from "@/components/RepCard";

interface CandidateCardProps {
  candidate: Candidate;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  onResearch: () => void;
}

export function CandidateCard({
  candidate,
  researchStatus,
  summary,
  onResearch,
}: CandidateCardProps) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4">
        <div className="flex items-center gap-3 mb-3">
          {candidate.photo_url ? (
            <img
              src={candidate.photo_url}
              alt={candidate.name}
              className="w-10 h-10 rounded-full object-cover border border-muted flex-shrink-0"
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground text-sm font-semibold flex-shrink-0">
              {candidate.name.charAt(0)}
            </div>
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-sm">{candidate.name}</span>
              {candidate.incumbent && (
                <Badge variant="outline" className="text-xs">Incumbent</Badge>
              )}
            </div>
            <span className="text-xs text-muted-foreground">
              {candidate.party || "No party"}
            </span>
          </div>
        </div>

        {researchStatus === "idle" && (
          <Button onClick={onResearch} variant="outline" size="sm" className="w-full">
            Generate AI Research
          </Button>
        )}

        {researchStatus === "loading" && !summary && (
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground italic">Researching...</p>
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        )}

        {researchStatus === "loading" && summary && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-3 w-3 group-data-[state=open]:hidden" />
              <ChevronDown className="h-3 w-3 group-data-[state=closed]:hidden" />
              AI Research (loading...)
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "complete" && summary && (
          <Collapsible>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-3 w-3 group-data-[state=open]:hidden" />
              <ChevronDown className="h-3 w-3 group-data-[state=closed]:hidden" />
              AI Research
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
            </CollapsibleContent>
          </Collapsible>
        )}

        {researchStatus === "failed" && (
          <Button onClick={onResearch} variant="outline" size="sm" className="w-full">
            Retry Research
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
