import { useEffect, useMemo } from "react";
import { useAddress } from "@/contexts/AddressContext";
import { useElectionsQuery } from "@/hooks/useElectionsQuery";
import { useElectionResearchQuery as useElectionResearch } from "@/hooks/useElectionResearchQuery";
import { useResearchQuery as useResearch } from "@/hooks/useResearchQuery";
import { ElectionCard } from "@/components/ElectionCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import type { Candidate, Representative } from "@/types";

function candidateToRep(candidate: Candidate): Representative {
  return {
    name: candidate.name,
    office: candidate.office,
    level: candidate.level,
    party: candidate.party,
    photo_url: candidate.photo_url,
    contact: { website: null, phone: null, email: null },
  };
}

export function ElectionsPage() {
  const { address } = useAddress();
  const { data, isLoading, error } = useElectionsQuery(address);
  const elections = data?.elections ?? [];
  const researchIds = useMemo(() => data?.researchIds ?? {}, [data?.researchIds]);
  const { trackElectionResearch, getElectionStatus, getElectionSummary } = useElectionResearch();
  const { requestResearch, getStatus, getSummary } = useResearch();

  // Start polling for auto-triggered election research once we have research IDs
  useEffect(() => {
    for (const [key, researchId] of Object.entries(researchIds)) {
      if (researchId === "cached") continue;
      const [name, date] = key.split("|");
      trackElectionResearch(name, date, researchId);
    }
  }, [researchIds, trackElectionResearch]);

  const handleCandidateResearch = (candidate: Candidate) => {
    requestResearch(candidateToRep(candidate));
  };

  return (
    <>
      {isLoading && (
        <div className="space-y-4">
          <p className="text-center text-sm text-muted-foreground">
            Looking up upcoming elections…
          </p>
          <div className="grid gap-4 grid-cols-1 max-w-4xl mx-auto">
            {Array.from({ length: 2 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="text-center p-6 rounded-lg bg-destructive/10 text-destructive">
          {error.message}
        </div>
      )}

      {!isLoading && elections.length === 0 && !error && (
        <div className="text-center p-8">
          <p className="text-muted-foreground">
            No upcoming elections found for your address.
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            Election data becomes available when election authorities publish ballot information.
          </p>
        </div>
      )}

      {elections.length > 0 && (
        <div className="space-y-6 max-w-4xl mx-auto">
          {elections.map((election) => (
            <ElectionCard
              key={`${election.name}-${election.date}`}
              election={election}
              researchStatus={getElectionStatus(election.name, election.date)}
              researchSummary={getElectionSummary(election.name, election.date)}
              candidateToRep={candidateToRep}
              getCandidateResearchStatus={(c) => getStatus(candidateToRep(c))}
              getCandidateResearchSummary={(c) => getSummary(candidateToRep(c))}
              onCandidateResearch={handleCandidateResearch}
            />
          ))}
        </div>
      )}
    </>
  );
}
