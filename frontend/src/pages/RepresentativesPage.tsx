import { ChevronDown, ChevronRight } from "lucide-react";
import { RepCard } from "@/components/RepCard";
import { SkeletonCard } from "@/components/SkeletonCard";
import { sortBySeniority } from "@/lib/seniority";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useRepresentativesQuery } from "@/hooks/useRepresentativesQuery";
import { useResearchQuery as useResearch } from "@/hooks/useResearchQuery";
import { useAddress } from "@/contexts/AddressContext";
import type { Representative } from "@/types";
import { CrossLinkCards } from "@/components/CrossLinkCards";
import { formatDistrictBreakdown } from "@/lib/districts";

function groupByLevel(reps: Representative[]) {
  const groups: { label: string; level: string; reps: Representative[] }[] = [
    { label: "Federal", level: "federal", reps: [] },
    { label: "State", level: "state", reps: [] },
    { label: "Municipal", level: "municipal", reps: [] },
  ];
  for (const rep of reps) {
    const group = groups.find((g) => g.level === rep.level);
    if (group) group.reps.push(rep);
    else groups[2].reps.push(rep);
  }
  return groups.map((g) => ({ ...g, reps: sortBySeniority(g.reps) }));
}

export function RepresentativesPage() {
  const { address } = useAddress();
  const { data, isLoading, error } = useRepresentativesQuery(address);
  const representatives = data?.representatives ?? [];
  const districtInfo = data?.district_info ?? null;
  const { requestResearch, getStatus, getSummary } = useResearch();

  const hasResults = representatives.length > 0;
  const groups = groupByLevel(representatives);
  const districtBreakdown = districtInfo ? formatDistrictBreakdown(districtInfo) : null;
  const hasBreakdown =
    !!districtBreakdown &&
    (districtBreakdown.federal || districtBreakdown.state || districtBreakdown.municipal);

  return (
    <>
      {isLoading && !hasResults && (
        <div className="space-y-4">
          <p className="text-center text-sm text-muted-foreground">
            Looking up your representatives…
          </p>
          <div className="grid gap-4 grid-cols-1 max-w-4xl mx-auto">
            {Array.from({ length: 6 }).map((_, i) => (
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

      {hasResults && (
        <div className="space-y-8">
          {hasBreakdown && districtBreakdown && (
            <div className="max-w-4xl mx-auto rounded-lg border bg-muted/30 p-4 text-sm">
              <p className="mb-2 text-muted-foreground">
                Based on your address, here's where you live in each level of government:
              </p>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
                {districtBreakdown.federal && (
                  <>
                    <dt className="font-semibold">Federal</dt>
                    <dd>
                      {districtBreakdown.federal}
                      <span className="text-muted-foreground"> — picks your U.S. House Representative</span>
                    </dd>
                  </>
                )}
                {districtBreakdown.state && (
                  <>
                    <dt className="font-semibold">State</dt>
                    <dd>
                      {districtBreakdown.state}
                      <span className="text-muted-foreground"> — picks your state legislators</span>
                    </dd>
                  </>
                )}
                {districtBreakdown.municipal && (
                  <>
                    <dt className="font-semibold">Municipal</dt>
                    <dd>
                      {districtBreakdown.municipal}
                      <span className="text-muted-foreground"> — your city/town government</span>
                    </dd>
                  </>
                )}
              </dl>
            </div>
          )}
          {groups.map((group) => (
            <Collapsible key={group.level} defaultOpen asChild>
              <section className="max-w-4xl mx-auto">
                <CollapsibleTrigger className="flex w-full items-center gap-2 border-b pb-2 cursor-pointer group">
                  <span className="text-muted-foreground transition-transform group-data-[state=closed]:rotate-0 group-data-[state=open]:rotate-0">
                    <ChevronRight className="h-5 w-5 group-data-[state=open]:hidden" />
                    <ChevronDown className="h-5 w-5 group-data-[state=closed]:hidden" />
                  </span>
                  <h2 className="text-2xl font-semibold">
                    {group.label}
                  </h2>
                  <span className="text-sm text-muted-foreground">
                    ({group.reps.length})
                  </span>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <div className="grid gap-4 grid-cols-1 mt-4">
                    {group.reps.length === 0 ? (
                      <p className="text-sm text-muted-foreground py-2">
                        We couldn't find {group.label.toLowerCase()} representatives for this address.
                      </p>
                    ) : (
                      group.reps.map((rep) => (
                        <RepCard
                          key={`${rep.name}-${rep.office}`}
                          rep={rep}
                          researchStatus={getStatus(rep)}
                          summary={getSummary(rep)}
                          onResearch={() => requestResearch(rep)}
                        />
                      ))
                    )}
                  </div>
                </CollapsibleContent>
              </section>
            </Collapsible>
          ))}
          <CrossLinkCards />
        </div>
      )}
    </>
  );
}
