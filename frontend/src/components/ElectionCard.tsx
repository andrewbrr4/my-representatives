import type {
  Election,
  ElectionResearchSummary,
  Candidate,
  Representative,
  Citation,
} from "@/types";
import type { ElectionResearchStatus } from "@/hooks/useElectionResearchQuery";
import type { ResearchStatus } from "@/hooks/useResearchQuery";
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

function ElectionParagraphSection({
  title,
  content,
  citations,
}: {
  title: string;
  content: string | null;
  citations: Citation[];
}) {
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

function ElectionListSection({
  title,
  items,
  citations,
}: {
  title: string;
  items: string[] | null;
  citations: Citation[];
}) {
  if (items === null) {
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
      <ul className="list-disc pl-5 space-y-1 text-sm leading-relaxed">
        {items.map((item, i) => (
          <li key={i}>{renderInline(item, citations)}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Parse a raw hours string like "Fri, Mar 6: 8 am - 5 pm Mon, Mar 9: 8 am - 5 pm ..."
 * into grouped date ranges by hours, e.g. "Mon Mar 6 – Fri Apr 18: 8 am - 5 pm"
 */
function parseEarlyVoteHours(raw: string): { dates: string; hours: string }[] {
  const entryPattern = /([A-Z][a-z]{2}),?\s+([A-Z][a-z]{2}\s+\d{1,2}):\s*(\d{1,2}(?::\d{2})?\s*[ap]m\s*-\s*\d{1,2}(?::\d{2})?\s*[ap]m)/g;
  const entries: { day: string; date: string; hours: string }[] = [];
  let m: RegExpExecArray | null;
  while ((m = entryPattern.exec(raw)) !== null) {
    entries.push({ day: m[1], date: m[2].trim(), hours: m[3].trim() });
  }

  if (entries.length === 0) return [{ dates: "", hours: raw }];

  // Group consecutive entries with the same hours into ranges
  const groups: { startDay: string; startDate: string; endDay: string; endDate: string; hours: string }[] = [];
  for (const entry of entries) {
    const last = groups.length > 0 ? groups[groups.length - 1] : null;
    if (last && last.hours === entry.hours) {
      last.endDay = entry.day;
      last.endDate = entry.date;
    } else {
      groups.push({
        startDay: entry.day,
        startDate: entry.date,
        endDay: entry.day,
        endDate: entry.date,
        hours: entry.hours,
      });
    }
  }

  return groups.map((g) => ({
    dates: g.startDate === g.endDate
      ? `${g.startDay}, ${g.startDate}`
      : `${g.startDay}, ${g.startDate} – ${g.endDay}, ${g.endDate}`,
    hours: g.hours,
  }));
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
  candidateToRep: (candidate: Candidate) => Representative;
  getCandidateResearchStatus: (candidate: Candidate) => ResearchStatus;
  getCandidateResearchSummary: (candidate: Candidate) => ResearchSummary | null;
  onCandidateResearch: (candidate: Candidate) => void;
}

export function ElectionCard({
  election,
  researchStatus,
  researchSummary,
  candidateToRep,
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
                <ElectionParagraphSection
                  title="About This Election"
                  content={researchSummary?.election_context ?? null}
                  citations={[]}
                />
                <ElectionListSection
                  title="Key Issues & Significance"
                  items={
                    // Only reveal once the preceding section is complete
                    researchSummary?.election_context != null
                      ? (researchSummary?.key_issues_and_significance ?? null)
                      : null
                  }
                  citations={researchSummary?.citations ?? []}
                />
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
                  <div key={i} className="text-sm mt-1">
                    <div className="font-medium">{site.name} — {site.address}</div>
                    {site.hours && (
                      <div className="text-muted-foreground mt-0.5">
                        {parseEarlyVoteHours(site.hours).map((slot, j) => (
                          <div key={j}>
                            {slot.dates ? `${slot.dates}: ${slot.hours}` : slot.hours}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
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
                  <div className="space-y-4">
                    {contest.candidates.map((candidate) => (
                      <CandidateCard
                        key={`${candidate.name}-${candidate.office}`}
                        candidate={candidate}
                        rep={candidateToRep(candidate)}
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
