import type {
  Election,
  ElectionResearchSummary,
  Candidate,
  Citation,
} from "@/types";
import type { ElectionResearchStatus } from "@/hooks/useElectionResearch";
import type { ResearchStatus } from "@/hooks/useResearch";
import type { ResearchSummary } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ChevronDown, ChevronRight } from "lucide-react";
import { CandidateCard } from "@/components/CandidateCard";
import { renderInline } from "@/components/RepCard";

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T00:00:00");
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

function renderElectionSection(
  title: string,
  content: string | null,
  citations: Citation[]
) {
  if (content === null) {
    return (
      <div>
        <h4 className="text-xs font-medium text-muted-foreground mb-1">{title}</h4>
        <div className="space-y-1">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-5/6" />
        </div>
      </div>
    );
  }
  return (
    <div>
      <h4 className="text-xs font-medium text-muted-foreground mb-1">{title}</h4>
      <p className="text-sm leading-relaxed">{renderInline(content, citations)}</p>
    </div>
  );
}

const typeColors: Record<string, string> = {
  primary: "bg-purple-600 text-white",
  general: "bg-blue-600 text-white",
  runoff: "bg-amber-600 text-white",
};

interface ElectionCardProps {
  election: Election;
  researchStatus: ElectionResearchStatus;
  researchSummary: ElectionResearchSummary | null;
  getCandidateResearchStatus: (candidate: Candidate) => ResearchStatus;
  getCandidateResearchSummary: (candidate: Candidate) => ResearchSummary | null;
  onCandidateResearch: (candidate: Candidate) => void;
}

export function ElectionCard({
  election,
  researchStatus,
  researchSummary,
  getCandidateResearchStatus,
  getCandidateResearchSummary,
  onCandidateResearch,
}: ElectionCardProps) {
  const days = daysUntil(election.date);
  const daysLabel = days === 0 ? "Today" : days === 1 ? "Tomorrow" : `${days} days away`;

  return (
    <Card className="overflow-hidden">
      <CardHeader>
        <div className="flex justify-between items-start">
          <div>
            <Badge className={typeColors[election.election_type] || typeColors.general}>
              {election.election_type}
            </Badge>
            <CardTitle className="text-xl mt-2">{election.name}</CardTitle>
          </div>
          <div className="text-right">
            <div className="font-medium">{election.date}</div>
            <div className="text-sm text-muted-foreground">{daysLabel}</div>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* AI Election Context */}
        {(researchStatus === "loading" || researchStatus === "complete") && (
          <Collapsible defaultOpen>
            <CollapsibleTrigger className="flex w-full items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground cursor-pointer group">
              <ChevronRight className="h-4 w-4 group-data-[state=open]:hidden" />
              <ChevronDown className="h-4 w-4 group-data-[state=closed]:hidden" />
              AI Election Context
              {researchStatus === "loading" && (
                <span className="ml-1 text-xs italic">(loading...)</span>
              )}
            </CollapsibleTrigger>
            <CollapsibleContent>
              <div className="space-y-3 mt-2 p-4 rounded-lg bg-muted/30 border">
                {renderElectionSection(
                  "About This Election",
                  researchSummary?.election_context ?? null,
                  []
                )}
                {renderElectionSection(
                  "Key Issues & Significance",
                  researchSummary?.key_issues_and_significance ?? null,
                  researchSummary?.citations ?? []
                )}
              </div>
            </CollapsibleContent>
          </Collapsible>
        )}

        {/* Polling Location */}
        {election.polling_location && (
          <div className="p-3 rounded-lg bg-muted/30 border">
            <h4 className="text-xs font-medium text-muted-foreground mb-1">Polling Location</h4>
            <div className="text-sm font-medium">{election.polling_location.name}</div>
            <div className="text-sm text-muted-foreground">{election.polling_location.address}</div>
            {election.polling_location.hours && (
              <div className="text-sm text-muted-foreground">Hours: {election.polling_location.hours}</div>
            )}
          </div>
        )}

        {/* Voter Info */}
        {election.voter_info && (
          <div className="p-3 rounded-lg bg-muted/30 border space-y-2">
            <h4 className="text-xs font-medium text-muted-foreground">Voter Resources</h4>
            <div className="flex flex-wrap gap-3 text-sm">
              {election.voter_info.registration_url && (
                <a href={election.voter_info.registration_url} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2 hover:text-primary/80">Register to Vote</a>
              )}
              {election.voter_info.absentee_url && (
                <a href={election.voter_info.absentee_url} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2 hover:text-primary/80">Absentee/Mail-In Voting</a>
              )}
              {election.voter_info.ballot_info_url && (
                <a href={election.voter_info.ballot_info_url} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2 hover:text-primary/80">Ballot Information</a>
              )}
            </div>
            {election.voter_info.mail_only && (
              <p className="text-xs text-muted-foreground">This is a mail-only election.</p>
            )}
            {election.voter_info.early_vote_sites.length > 0 && (
              <div>
                <h5 className="text-xs text-muted-foreground font-medium mt-2">Early Vote Sites</h5>
                {election.voter_info.early_vote_sites.map((site, i) => (
                  <div key={i} className="text-sm">{site.name} — {site.address}{site.hours ? ` (${site.hours})` : ""}</div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* What's on your ballot */}
        {election.contests.length > 0 && (
          <div>
            <h3 className="font-semibold mb-4">What's on your ballot</h3>
            <div className="space-y-6">
              {election.contests.map((contest) => (
                <div key={contest.office}>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground border-b pb-1 mb-3">
                    {contest.office}
                    {contest.district_name && (
                      <span className="ml-1">— {contest.district_name}</span>
                    )}
                  </div>
                  <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
                    {contest.candidates.map((candidate) => (
                      <CandidateCard
                        key={`${candidate.name}-${candidate.office}`}
                        candidate={candidate}
                        researchStatus={getCandidateResearchStatus(candidate)}
                        summary={getCandidateResearchSummary(candidate)}
                        onResearch={() => onCandidateResearch(candidate)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {election.contests.length === 0 && (
          <p className="text-sm text-muted-foreground italic">
            Candidate information not yet available for this election.
          </p>
        )}

        <div className="border border-dashed rounded-lg p-4">
          <p className="text-sm text-muted-foreground italic">
            Referenda &amp; propositions — coming soon
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
