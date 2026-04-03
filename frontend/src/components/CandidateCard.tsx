import type { Candidate, Representative, ResearchSummary } from "@/types";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { ResearchContent } from "@/components/RepCard";
import { IssueSearch } from "@/components/IssueSearch";

const levelColors: Record<string, string> = {
  federal: "bg-blue-600 text-white hover:bg-blue-700",
  state: "bg-amber-600 text-white hover:bg-amber-700",
  municipal: "bg-emerald-600 text-white hover:bg-emerald-700",
};

interface CandidateCardProps {
  candidate: Candidate;
  rep: Representative;
  researchStatus: ResearchStatus;
  summary: ResearchSummary | null;
  onResearch: () => void;
}

export function CandidateCard({
  candidate,
  rep,
  researchStatus,
  summary,
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
          <div className="flex items-center gap-2 flex-wrap">
            <CardTitle className="text-lg">{candidate.name}</CardTitle>
            <Badge className={levelColors[candidate.level] || ""}>
              {candidate.level}
            </Badge>
            {candidate.incumbent && (
              <Badge variant="outline">Incumbent</Badge>
            )}
          </div>
          <CardDescription className="mt-1">
            {candidate.office}
            {candidate.party && ` · ${candidate.party}`}
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Issue search */}
        <IssueSearch rep={rep} />

        {/* Research states */}
        {researchStatus === "idle" && (
          <Button onClick={onResearch} variant="outline" className="w-full">
            Generate AI Overview
          </Button>
        )}

        {researchStatus === "loading" && !summary && (
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground italic">
              Scraping the web for information about this candidate -- this usually takes 30-60 seconds...
            </p>
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {researchStatus === "loading" && summary && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Overview
              <span className="ml-1 text-xs text-muted-foreground italic">(Scraping the web for information about this candidate -- this usually takes 30-60 seconds...)</span>
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
              AI Overview
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ResearchContent summary={summary} />
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
